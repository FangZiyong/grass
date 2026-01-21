#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
sync_md_to_feishu.py

能力：
1) 支持“映射表”批量同步：本地MD路径 -> 飞书Docx链接/ID -> 是否同步(1/0)
2) 每次同步：先清空正文（不改标题）再全量写入
3) 保留MD中 PlantUML 代码块位置：遇到 ```plantuml ...``` 就在该位置插入“画板块(block_type=43)”
   然后调用 Board PlantUML 接口把图渲染进该画板

依赖：
  pip install requests tqdm
"""

import os
import re
import time
import json
import random
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Set, Iterable

import requests
from requests import exceptions as req_exc
from tqdm import tqdm

FEISHU_OPENAPI_BASE = "https://open.feishu.cn/open-apis"

# ------------------------------
# 读取同目录 feishu.env
# ------------------------------
def load_env_file(env_path: str) -> Dict[str, str]:
    if not os.path.exists(env_path):
        return {}
    out: Dict[str, str] = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
                v = v[1:-1]
            out[k] = v
    return out


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, "feishu.env")
for k, v in load_env_file(ENV_PATH).items():
    os.environ.setdefault(k, v)

APP_ID = os.environ.get("FEISHU_APP_ID", os.environ.get("APP_ID", "")).strip()
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", os.environ.get("APP_SECRET", "")).strip()

# 批量模式（可选）
MAPPING_PATH = os.environ.get("FEISHU_MAPPING_PATH", "").strip()

# 单文档模式（可选）
DOCUMENT_ID = os.environ.get("FEISHU_DOCUMENT_ID", os.environ.get("DOCUMENT_ID", "")).strip()
LOCAL_MD_PATH = os.environ.get("FEISHU_MD_PATH", os.environ.get("LOCAL_MD_PATH", "")).strip()

# 插入父块
PARENT_BLOCK_ID = os.environ.get("FEISHU_PARENT_BLOCK_ID", os.environ.get("PARENT_BLOCK_ID", "")).strip()

# Board PlantUML 接口 Bearer（可 tenant 或 user）
BOARD_ACCESS_TOKEN = os.environ.get("FEISHU_BOARD_ACCESS_TOKEN", "").strip()
USER_ACCESS_TOKEN = os.environ.get("FEISHU_USER_ACCESS_TOKEN", "").strip()

MAX_DESCENDANTS = int(os.environ.get("FEISHU_MAX_DESCENDANTS", "1000").strip() or "1000")
ALWAYS_CLEAR_BEFORE_SYNC = os.environ.get("FEISHU_ALWAYS_CLEAR_BEFORE_SYNC", "1").strip().lower() in ("1", "true", "yes")
CLEAR_PAGE_SIZE = int(os.environ.get("FEISHU_CLEAR_PAGE_SIZE", "200").strip() or "200")
PRESPLIT_THRESHOLD = int(os.environ.get("FEISHU_PRESPLIT_THRESHOLD", "0").strip() or "0")

if not APP_ID or not APP_SECRET:
    raise RuntimeError("缺少 FEISHU_APP_ID / FEISHU_APP_SECRET")

if MAPPING_PATH:
    if not os.path.exists(MAPPING_PATH):
        raise RuntimeError(f"FEISHU_MAPPING_PATH 不存在：{MAPPING_PATH}")
else:
    if not DOCUMENT_ID or not LOCAL_MD_PATH:
        raise RuntimeError("单文档模式缺少 FEISHU_DOCUMENT_ID / FEISHU_MD_PATH（或改用 FEISHU_MAPPING_PATH）")

# ------------------------------
# HTTP：429/5xx 退避重试 + 10s 超时重试 + 全量请求日志
# ------------------------------
MAX_RETRIES = 8          # 仅用于 429/5xx 的退避重试（总尝试次数上限）
BASE_SLEEP = 0.8
JITTER = 0.3

HTTP_SESSION = requests.Session()

# 超时控制（你要的：10 秒超时 + 最多重试 3 次）
HTTP_READ_TIMEOUT_S = float(os.environ.get("FEISHU_HTTP_TIMEOUT", "10").strip() or "10")              # read timeout
HTTP_CONNECT_TIMEOUT_S = float(os.environ.get("FEISHU_HTTP_CONNECT_TIMEOUT", "3").strip() or "3")     # connect timeout
HTTP_TIMEOUT_MAX_RETRY = int(os.environ.get("FEISHU_HTTP_TIMEOUT_RETRY", "3").strip() or "3")         # 不含首次

# 请求日志开关 & payload 摘要长度
HTTP_LOG_ENABLED = os.environ.get("FEISHU_HTTP_LOG", "1").strip().lower() in ("1", "true", "yes", "y")
HTTP_LOG_PAYLOAD_MAXLEN = int(os.environ.get("FEISHU_HTTP_LOG_PAYLOAD_MAXLEN", "220").strip() or "220")


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _tqdm_print(line: str) -> None:
    if not HTTP_LOG_ENABLED:
        return
    try:
        tqdm.write(line)
    except Exception:
        print(line)


def _pretty(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj)


def _mask(s: str, keep_head: int = 10, keep_tail: int = 6) -> str:
    if not s:
        return s
    s = str(s)
    if len(s) <= keep_head + keep_tail + 3:
        return s
    return f"{s[:keep_head]}***{s[-keep_tail:]}"


def _sanitize_headers(headers: dict) -> dict:
    out = {}
    for k, v in (headers or {}).items():
        if k.lower() == "authorization":
            out[k] = _mask(v, 14, 6)
        else:
            out[k] = v
    return out


def _summarize_json_body(json_body: Any) -> str:
    """
    避免把 markdown content 整段打印出来：遇到 content 字段只打印长度 + 片段
    """
    if json_body is None:
        return ""
    try:
        if isinstance(json_body, dict):
            jb = dict(json_body)
            if "content" in jb and isinstance(jb["content"], str):
                c = jb["content"]
                snippet = c[:HTTP_LOG_PAYLOAD_MAXLEN].replace("\n", "\\n")
                jb["content"] = f"<str len={len(c)} snip='{snippet}...'>"
            s = json.dumps(jb, ensure_ascii=False)
        else:
            s = json.dumps(json_body, ensure_ascii=False)
    except Exception:
        s = str(json_body)

    if len(s) > HTTP_LOG_PAYLOAD_MAXLEN:
        return s[:HTTP_LOG_PAYLOAD_MAXLEN] + "..."
    return s


def request_json(method: str, url: str, *, headers=None, params=None, json_body=None, hint="request") -> Dict:
    """
    - 每次请求打印：method/url/params/json摘要/耗时/status/feishu_logid
    - 读超时 10s（可通过 FEISHU_HTTP_TIMEOUT 调整），超时自动重试，最多 3 次（不含首次）
    - 对 429/5xx 做指数退避重试（MAX_RETRIES 次总尝试上限）
    """
    headers = headers or {}
    params = params or {}

    req_trace = uuid.uuid4().hex[:10]
    last_text = ""
    last_status = None

    timeout_retry_used = 0  # 不含首次
    backoff_retry_used = 0  # 只统计 429/5xx 的退避重试次数

    while True:
        safe_headers = _sanitize_headers(headers)
        body_summary = _summarize_json_body(json_body)

        _tqdm_print(
            f"[{_ts()}][HTTP][{req_trace}][{hint}] -> {method} {url} "
            f"timeout_retry={timeout_retry_used}/{HTTP_TIMEOUT_MAX_RETRY} "
            f"backoff_retry={backoff_retry_used}/{MAX_RETRIES-1} "
            f"params={params if params else {}} headers={safe_headers} json={body_summary}"
        )

        t0 = time.time()
        try:
            resp = HTTP_SESSION.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=(HTTP_CONNECT_TIMEOUT_S, HTTP_READ_TIMEOUT_S),
            )
        except (req_exc.ReadTimeout, req_exc.ConnectTimeout, req_exc.Timeout) as e:
            dt = time.time() - t0
            timeout_retry_used += 1
            _tqdm_print(f"[{_ts()}][HTTP][{req_trace}][{hint}] !! TIMEOUT after {dt:.2f}s err={repr(e)}")

            if timeout_retry_used <= HTTP_TIMEOUT_MAX_RETRY:
                sleep_s = min(0.6 * (2 ** (timeout_retry_used - 1)) + random.random() * JITTER, 6.0)
                _tqdm_print(f"[{_ts()}][HTTP][{req_trace}][{hint}] .. retry(timeout) sleep {sleep_s:.2f}s")
                time.sleep(sleep_s)
                continue

            raise RuntimeError(
                f"{hint} 超时重试耗尽（connect_timeout={HTTP_CONNECT_TIMEOUT_S}s, read_timeout={HTTP_READ_TIMEOUT_S}s, "
                f"max_timeout_retry={HTTP_TIMEOUT_MAX_RETRY}）\n"
                f"method={method} url={url} params={params}"
            ) from e

        except req_exc.RequestException as e:
            dt = time.time() - t0
            _tqdm_print(f"[{_ts()}][HTTP][{req_trace}][{hint}] !! RequestException after {dt:.2f}s err={repr(e)}")

            # 把其他网络错误也按退避重试处理（算在 backoff_retry_used 里）
            if backoff_retry_used < MAX_RETRIES - 1:
                sleep_s = min(BASE_SLEEP * (2 ** backoff_retry_used) + random.random() * JITTER, 10.0)
                backoff_retry_used += 1
                _tqdm_print(f"[{_ts()}][HTTP][{req_trace}][{hint}] .. retry(neterr) sleep {sleep_s:.2f}s")
                time.sleep(sleep_s)
                continue

            raise RuntimeError(
                f"{hint} 网络错误重试耗尽（MAX_RETRIES={MAX_RETRIES}）\n"
                f"method={method} url={url} params={params}\n"
                f"last_error={repr(e)}"
            ) from e

        dt = time.time() - t0
        last_status = resp.status_code
        last_text = (resp.text or "")[:2000]

        feishu_logid = (
            resp.headers.get("X-Tt-Logid")
            or resp.headers.get("x-tt-logid")
            or resp.headers.get("X-Request-Id")
            or resp.headers.get("x-request-id")
            or ""
        )
        _tqdm_print(
            f"[{_ts()}][HTTP][{req_trace}][{hint}] <- status={resp.status_code} cost={dt:.2f}s "
            f"len={len(resp.text or '')} feishu_logid={feishu_logid}"
        )

        # 429/5xx：指数退避
        if resp.status_code == 429 or 500 <= resp.status_code <= 599:
            if backoff_retry_used < MAX_RETRIES - 1:
                sleep_s = BASE_SLEEP * (2 ** backoff_retry_used) + random.random() * JITTER
                ra = resp.headers.get("Retry-After")
                if ra:
                    try:
                        sleep_s = max(sleep_s, float(ra))
                    except Exception:
                        pass
                backoff_retry_used += 1
                _tqdm_print(f"[{_ts()}][HTTP][{req_trace}][{hint}] .. retry({resp.status_code}) sleep {sleep_s:.2f}s")
                time.sleep(sleep_s)
                continue

            raise RuntimeError(
                f"{hint} 429/5xx 重试次数耗尽（MAX_RETRIES={MAX_RETRIES}） last_http={last_status}\n"
                f"method={method} url={url}\nresp={last_text}"
            )

        try:
            data = resp.json()
        except Exception as e:
            raise RuntimeError(
                f"{hint} 返回非 JSON，HTTP {resp.status_code}\n"
                f"method={method} url={url}\n"
                f"resp={last_text}"
            ) from e

        if isinstance(data, dict):
            _tqdm_print(f"[{_ts()}][HTTP][{req_trace}][{hint}] json.code={data.get('code')} msg={data.get('msg', '')}")

        return data


def raise_if_fail(data: Dict[str, Any], *, hint: str, extra: Optional[Dict[str, Any]] = None) -> None:
    if data.get("code") == 0:
        return
    err = data.get("error") or {}
    log_id = err.get("log_id") or data.get("log_id")
    msg = data.get("msg") or ""
    more = {"log_id": log_id} if log_id else {}
    if extra:
        more.update(extra)
    raise RuntimeError(f"{hint} 失败: code={data.get('code')} msg={msg} extra={_pretty(more)} resp={_pretty(data)}")


# ------------------------------
# Token
# ------------------------------
def get_tenant_access_token() -> str:
    url = f"{FEISHU_OPENAPI_BASE}/auth/v3/tenant_access_token/internal"
    data = request_json("POST", url, json_body={"app_id": APP_ID, "app_secret": APP_SECRET}, hint="tenant_access_token")
    raise_if_fail(data, hint="获取 tenant_access_token")
    return data["tenant_access_token"]


def pick_board_bearer(token_docx: str) -> str:
    if BOARD_ACCESS_TOKEN:
        return BOARD_ACCESS_TOKEN
    if USER_ACCESS_TOKEN:
        return USER_ACCESS_TOKEN
    return token_docx


# ------------------------------
# Doc 元信息：读取标题 / 更新标题
# ------------------------------
def get_document_meta(document_id: str, token_docx: str) -> Dict[str, Any]:
    url = f"{FEISHU_OPENAPI_BASE}/docx/v1/documents/{document_id}"
    headers = {"Authorization": f"Bearer {token_docx}"}
    data = request_json("GET", url, headers=headers, hint="get_document_meta")
    raise_if_fail(data, hint="读取文档 meta")
    return data.get("data") or {}


def update_document_title(document_id: str, token_docx: str, title: str) -> None:
    url = f"{FEISHU_OPENAPI_BASE}/docx/v1/documents/{document_id}"
    headers = {"Authorization": f"Bearer {token_docx}", "Content-Type": "application/json; charset=utf-8"}
    data = request_json("PATCH", url, headers=headers, json_body={"title": title}, hint="update_document_title")
    raise_if_fail(data, hint="更新文档标题")


# ------------------------------
# Docx Convert
# ------------------------------
def convert_markdown(md: str, token_docx: str) -> Dict[str, Any]:
    url = f"{FEISHU_OPENAPI_BASE}/docx/v1/documents/blocks/convert"
    headers = {"Authorization": f"Bearer {token_docx}", "Content-Type": "application/json; charset=utf-8"}
    payload = {"content_type": "markdown", "content": md}
    data = request_json("POST", url, headers=headers, json_body=payload, hint="convert")
    raise_if_fail(data, hint="convert_markdown")
    return data.get("data") or {}


# ------------------------------
# 顺序 & 块池提取（优先 first_level_block_ids）
# ------------------------------
def extract_order_and_pool(convert_data: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, Any]]]:
    pool = convert_data.get("descendants")
    if not isinstance(pool, list) or not pool:
        pool = convert_data.get("blocks") or convert_data.get("block_list") or []
    if not isinstance(pool, list) or not pool:
        raise RuntimeError(f"convert 返回里找不到 descendants/blocks: keys={list(convert_data.keys())}")

    first_level = convert_data.get("first_level_block_ids")
    if isinstance(first_level, list) and first_level:
        return first_level, pool

    children_id = convert_data.get("children_id")
    if isinstance(children_id, list) and children_id:
        return children_id, pool

    referenced: Set[str] = set()
    for b in pool:
        for cid in b.get("children", []) or []:
            if isinstance(cid, str):
                referenced.add(cid)

    roots = []
    for b in pool:
        bid = b.get("block_id")
        if bid and bid not in referenced:
            roots.append(bid)

    if not roots:
        raise RuntimeError("无法推断顶层顺序（first_level_block_ids/children_id 均不存在且 roots 为空）")
    return roots, pool


def build_block_map(pool: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    m: Dict[str, Dict[str, Any]] = {}
    for b in pool:
        bid = b.get("block_id")
        if bid:
            m[bid] = b
    return m


def collect_subtree(block_map: Dict[str, Dict[str, Any]], root_id: str) -> List[Dict[str, Any]]:
    res: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    def dfs(bid: str):
        if bid in seen:
            return
        b = block_map.get(bid)
        if not b:
            return
        seen.add(bid)
        res.append(b)
        ch = b.get("children") or []
        if isinstance(ch, list):
            for cid in ch:
                if isinstance(cid, str):
                    dfs(cid)

    dfs(root_id)
    return res


# ------------------------------
# 清洗 convert 的 block 对象
# ------------------------------
DROP_KEYS = {
    "revision_id", "create_time", "update_time",
    "update_user", "owner_id", "tenant_id",
    "document_id", "parent_id", "parent_type",
    "extra", "meta", "style", "layout",
    "merge_info",
}

def sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            if k in DROP_KEYS:
                obj.pop(k, None)

        bt = obj.get("block_type")
        if bt == 12 and "unordered" in obj and "bullet" not in obj:
            obj["bullet"] = obj.pop("unordered")

        for k, v in list(obj.items()):
            obj[k] = sanitize(v)
        return obj

    if isinstance(obj, list):
        return [sanitize(x) for x in obj]

    return obj


# ------------------------------
# Docx children：list & delete by index（用于清空正文）
# ------------------------------
def get_children_first_page(document_id: str, block_id: str, token_docx: str, page_size: int = 200) -> List[str]:
    headers = {"Authorization": f"Bearer {token_docx}"}
    url = f"{FEISHU_OPENAPI_BASE}/docx/v1/documents/{document_id}/blocks/{block_id}/children"
    params = {"page_size": page_size}
    data = request_json("GET", url, headers=headers, params=params, hint="get_children_first_page")
    raise_if_fail(data, hint="获取 children")
    items = data.get("data", {}).get("items") or []
    return [it.get("block_id") for it in items if it.get("block_id")]


def batch_delete_children_by_index(document_id: str, block_id: str, token_docx: str, start_index: int, end_index: int) -> None:
    headers = {"Authorization": f"Bearer {token_docx}", "Content-Type": "application/json; charset=utf-8"}
    url = f"{FEISHU_OPENAPI_BASE}/docx/v1/documents/{document_id}/blocks/{block_id}/children/batch_delete"
    payload = {"start_index": start_index, "end_index": end_index}
    data = request_json("DELETE", url, headers=headers, json_body=payload, hint="batch_delete_children")
    raise_if_fail(data, hint="batch_delete_children")


def clear_document_body_keep_title(document_id: str, token_docx: str) -> None:
    meta = get_document_meta(document_id, token_docx)
    title = meta.get("title") or ""
    body_root = document_id

    while True:
        ids = get_children_first_page(document_id, body_root, token_docx, page_size=CLEAR_PAGE_SIZE)
        if not ids:
            break
        batch_delete_children_by_index(document_id, body_root, token_docx, start_index=0, end_index=len(ids))
        time.sleep(0.15)

    if title:
        update_document_title(document_id, token_docx, title)


# ------------------------------
# Docx：descendant 写入
# ------------------------------
def insert_descendant(
    document_id: str,
    parent_block_id: str,
    token_docx: str,
    children_id: List[str],
    descendants: List[Dict[str, Any]],
    index: int
) -> Dict[str, Any]:
    url = f"{FEISHU_OPENAPI_BASE}/docx/v1/documents/{document_id}/blocks/{parent_block_id}/descendant"
    headers = {"Authorization": f"Bearer {token_docx}", "Content-Type": "application/json; charset=utf-8"}
    payload = {"children_id": children_id, "descendants": descendants, "index": index}
    return request_json("POST", url, headers=headers, json_body=payload, hint="descendant_insert")


def is_too_many_descendants_error(resp: Dict[str, Any]) -> bool:
    try:
        err = resp.get("error") or {}
        fvs = err.get("field_violations") or []
        for fv in fvs:
            if fv.get("field") == "descendants" and "max len" in (fv.get("description") or ""):
                return True
    except Exception:
        pass
    msg = (resp.get("msg") or "").lower()
    return ("descendants" in msg and "max len" in msg) or ("max len" in msg and "descendants" in msg)


def sync_one_chunk_markdown_to_docx(
    md_chunk: str,
    document_id: str,
    parent_block_id: str,
    token_docx: str,
    index: int,
) -> Tuple[bool, int, Dict[str, Any]]:
    if not md_chunk or not md_chunk.strip():
        return True, index, {"code": 0, "msg": "skip empty md"}

    cdata = convert_markdown(md_chunk, token_docx)
    order_ids, pool = extract_order_and_pool(cdata)

    pool = sanitize(pool)
    block_map = build_block_map(pool)

    descendants: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for rid in order_ids:
        for b in collect_subtree(block_map, rid):
            bid = b.get("block_id")
            if bid and bid not in seen:
                seen.add(bid)
                descendants.append(b)

    if len(descendants) > MAX_DESCENDANTS:
        fake = {
            "code": 99992402,
            "msg": "field validation failed",
            "error": {"field_violations": [{"field": "descendants", "description": f"the max len is {MAX_DESCENDANTS}"}]},
        }
        return False, index, fake

    resp = insert_descendant(document_id, parent_block_id, token_docx, order_ids, descendants, index)
    if resp.get("code") != 0:
        return False, index, resp

    return True, index + len(order_ids), resp


# ------------------------------
# Docx：创建 children（用于插入画板块 block_type=43）
# ------------------------------
def create_children_blocks(
    document_id: str,
    parent_block_id: str,
    token_docx: str,
    *,
    children: List[Dict[str, Any]],
    index: int
) -> Dict[str, Any]:
    url = f"{FEISHU_OPENAPI_BASE}/docx/v1/documents/{document_id}/blocks/{parent_block_id}/children"
    headers = {"Authorization": f"Bearer {token_docx}", "Content-Type": "application/json; charset=utf-8"}
    payload = {"children": children, "index": index}
    return request_json("POST", url, headers=headers, json_body=payload, hint="create_children_blocks")


def create_board_block_and_get_whiteboard_id(
    document_id: str,
    parent_block_id: str,
    token_docx: str,
    *,
    index: int
) -> Tuple[str, str]:
    """
    ✅ 修复：返回字段是 data.children（不是 data.items）
    """
    resp = create_children_blocks(
        document_id,
        parent_block_id,
        token_docx,
        children=[{"block_type": 43, "board": {}}],
        index=index,
    )
    raise_if_fail(resp, hint="创建画板块(create_children_blocks)", extra={"index": index, "parent_block_id": parent_block_id})

    data = resp.get("data") or {}
    children_list = data.get("children") or []
    if not children_list:
        raise RuntimeError(f"创建画板块返回 children 为空: resp={_pretty(resp)}")

    blk = children_list[0]
    block_id = blk.get("block_id")
    whiteboard_id = (blk.get("board") or {}).get("token")

    if not block_id:
        raise RuntimeError(f"创建画板块未返回 block_id: blk={_pretty(blk)}")
    if not whiteboard_id:
        raise RuntimeError(f"创建画板块未返回 board.token: blk={_pretty(blk)}")

    return block_id, whiteboard_id


# ------------------------------
# Board：PlantUML -> 画板节点
# ------------------------------
def create_plantuml_whiteboard_node(
    whiteboard_id: str,
    bearer_token: str,
    *,
    plant_uml_code: str,
    style_type: int = 1,
    syntax_type: int = 1,
    diagram_type: int = 0,
) -> Dict[str, Any]:
    url = f"{FEISHU_OPENAPI_BASE}/board/v1/whiteboards/{whiteboard_id}/nodes/plantuml"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "diagram_type": int(diagram_type),
        "plant_uml_code": plant_uml_code,
        "style_type": int(style_type),
        "syntax_type": int(syntax_type),
    }
    data = request_json("POST", url, headers=headers, json_body=payload, hint="create_plantuml_node")
    raise_if_fail(data, hint="plantuml 转画板(create plantuml node)", extra={"whiteboard_id": whiteboard_id})
    return data.get("data") or {}


# ------------------------------
# Markdown：按 H2/H3 切段
# ------------------------------
H2_RE = re.compile(r"(?m)^(##\s+.+)$")
H3_RE = re.compile(r"(?m)^(###\s+.+)$")

def split_by_heading(md: str, level: int) -> List[Tuple[str, str]]:
    if level == 2:
        pat = H2_RE
        prefix = "##"
    elif level == 3:
        pat = H3_RE
        prefix = "###"
    else:
        raise ValueError("level must be 2 or 3")

    lines = md.splitlines(True)
    idx = [i for i, line in enumerate(lines) if pat.match(line)]
    if not idx:
        return [("__ALL__", md)]

    sections: List[Tuple[str, str]] = []
    if idx[0] > 0:
        pre = "".join(lines[:idx[0]]).strip("\n")
        if pre.strip():
            sections.append(("__PREFACE__", pre + "\n"))

    for j, start in enumerate(idx):
        end = idx[j + 1] if j + 1 < len(idx) else len(lines)
        chunk = "".join(lines[start:end]).rstrip() + "\n"
        title = lines[start].strip()[len(prefix):].strip()
        sections.append((title, chunk))

    return sections


# ------------------------------
# Markdown：识别 PlantUML fenced code block，并保持原位置替换为画板
# ------------------------------
PLANTUML_FENCE_RE = re.compile(
    r"```(?:plantuml|puml|uml)\s*\n(.*?)\n```",
    re.IGNORECASE | re.DOTALL
)

def split_md_by_plantuml(md: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    last = 0
    for m in PLANTUML_FENCE_RE.finditer(md):
        pre = md[last:m.start()]
        if pre.strip():
            out.append(("md", pre))
        code = (m.group(1) or "").strip("\n")
        out.append(("plantuml", code))
        last = m.end()

    tail = md[last:]
    if tail.strip():
        out.append(("md", tail))
    return out


def estimate_descendants_count(md: str, token_docx: str) -> int:
    if not md.strip():
        return 0
    cdata = convert_markdown(md, token_docx)
    order_ids, pool = extract_order_and_pool(cdata)
    pool = sanitize(pool)
    block_map = build_block_map(pool)

    descendants: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for rid in order_ids:
        for b in collect_subtree(block_map, rid):
            bid = b.get("block_id")
            if bid and bid not in seen:
                seen.add(bid)
                descendants.append(b)
    return len(descendants)


def sync_md_piece_with_plantuml(
    md_piece: str,
    *,
    document_id: str,
    parent_block_id: str,
    token_docx: str,
    token_board: str,
    index: int,
) -> int:
    pieces = split_md_by_plantuml(md_piece)

    for typ, content in pieces:
        if typ == "md":
            ok, new_index, resp = sync_one_chunk_markdown_to_docx(
                content, document_id, parent_block_id, token_docx, index
            )
            if ok:
                index = new_index
                time.sleep(0.10)
                continue

            if is_too_many_descendants_error(resp):
                h3s = split_by_heading(content, level=3)
                for _, h3_md in h3s:
                    index = sync_md_piece_with_plantuml(
                        h3_md,
                        document_id=document_id,
                        parent_block_id=parent_block_id,
                        token_docx=token_docx,
                        token_board=token_board,
                        index=index,
                    )
                continue

            raise RuntimeError(f"[FAIL] md 片段写入失败 index={index} resp={_pretty(resp)}")

        else:
            _, whiteboard_id = create_board_block_and_get_whiteboard_id(
                document_id, parent_block_id, token_docx, index=index
            )

            create_plantuml_whiteboard_node(
                whiteboard_id,
                token_board,
                plant_uml_code=content,
                style_type=1,
                syntax_type=1,
                diagram_type=0,
            )

            index += 1
            time.sleep(0.10)

    return index


# ------------------------------
# 映射表：local_path \t docx_url_or_id \t sync_flag
# ------------------------------
DOCX_ID_RE = re.compile(r"/docx/([A-Za-z0-9]+)")

def parse_docx_id(docx_url_or_id: str) -> str:
    s = docx_url_or_id.strip()
    m = DOCX_ID_RE.search(s)
    if m:
        return m.group(1)
    return s

def iter_mapping_rows(path: str) -> Iterable[Tuple[str, str, bool]]:
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = re.split(r"\t|,", line)
            if len(parts) < 3:
                raise ValueError(f"mapping 行格式错误（需要3列）: {line}")
            local_path = parts[0].strip()
            docx = parts[1].strip()
            flag = parts[2].strip().lower()
            do_sync = flag in ("1", "true", "yes", "y")
            yield local_path, docx, do_sync


# ------------------------------
# 单文档同步：H2 循环
# ------------------------------
def sync_one_document(
    local_md_path: str,
    docx_id: str,
    token_docx: str,
    token_board: str,
    *,
    parent_block_id: str = "",
) -> None:
    if not os.path.exists(local_md_path):
        raise RuntimeError(f"本地MD不存在：{local_md_path}")

    with open(local_md_path, "r", encoding="utf-8") as f:
        md = f.read()

    if ALWAYS_CLEAR_BEFORE_SYNC:
        print(f"[INFO] 清空文档正文（保留标题） doc={docx_id}")
        clear_document_body_keep_title(docx_id, token_docx)
        print("[INFO] 清空完成")

    parent = parent_block_id or docx_id
    index = 0

    h2_sections = split_by_heading(md, level=2)
    print(f"[INFO] doc={docx_id} parent={parent} H2段数={len(h2_sections)}")

    for h2_title, h2_md in tqdm(h2_sections, desc=f"Sync {docx_id}", unit="sec"):
        if PRESPLIT_THRESHOLD > 0:
            try:
                est = estimate_descendants_count(h2_md, token_docx)
            except Exception:
                est = 0
            if est >= PRESPLIT_THRESHOLD:
                h3_sections = split_by_heading(h2_md, level=3)
                for _, h3_md in h3_sections:
                    index = sync_md_piece_with_plantuml(
                        h3_md,
                        document_id=docx_id,
                        parent_block_id=parent,
                        token_docx=token_docx,
                        token_board=token_board,
                        index=index,
                    )
                continue

        index = sync_md_piece_with_plantuml(
            h2_md,
            document_id=docx_id,
            parent_block_id=parent,
            token_docx=token_docx,
            token_board=token_board,
            index=index,
        )

    print(f"[DONE] doc={docx_id} 同步完成")


# ------------------------------
# main
# ------------------------------
def main():
    token_docx = get_tenant_access_token()
    print("[INFO] tenant_access_token OK")

    token_board = pick_board_bearer(token_docx)
    print("[INFO] board bearer ready")

    if MAPPING_PATH:
        for local_path, docx_url_or_id, do_sync in iter_mapping_rows(MAPPING_PATH):
            if not do_sync:
                print(f"[SKIP] {local_path} -> {docx_url_or_id}")
                continue
            docx_id = parse_docx_id(docx_url_or_id)
            print(f"[RUN ] {local_path} -> {docx_id}")
            sync_one_document(
                local_path,
                docx_id,
                token_docx,
                token_board,
                parent_block_id=PARENT_BLOCK_ID,
            )
        return

    sync_one_document(
        LOCAL_MD_PATH,
        DOCUMENT_ID,
        token_docx,
        token_board,
        parent_block_id=PARENT_BLOCK_ID,
    )


if __name__ == "__main__":
    main()
