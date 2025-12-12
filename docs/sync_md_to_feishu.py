#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import random
from typing import Any, Dict, List, Optional, Tuple, Set

import requests
from tqdm import tqdm

FEISHU_OPENAPI_BASE = "https://open.feishu.cn/open-apis"

# ------------------------------
# 读取同目录 feishu.env
# ------------------------------
def load_env_file(env_path: str) -> Dict[str, str]:
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"未找到 env 文件：{env_path}")
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
    os.environ[k] = v

APP_ID = os.environ.get("FEISHU_APP_ID", os.environ.get("APP_ID", "")).strip()
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", os.environ.get("APP_SECRET", "")).strip()
DOCUMENT_ID = os.environ.get("FEISHU_DOCUMENT_ID", os.environ.get("DOCUMENT_ID", "")).strip()
LOCAL_MD_PATH = os.environ.get("FEISHU_MD_PATH", os.environ.get("LOCAL_MD_PATH", "")).strip()

PARENT_BLOCK_ID = os.environ.get("FEISHU_PARENT_BLOCK_ID", os.environ.get("PARENT_BLOCK_ID", "")).strip()

MAX_DESCENDANTS = int(os.environ.get("FEISHU_MAX_DESCENDANTS", "1000").strip() or "1000")
ALWAYS_CLEAR_BEFORE_SYNC = os.environ.get("FEISHU_ALWAYS_CLEAR_BEFORE_SYNC", "1").strip().lower() in ("1", "true", "yes")

# 清空时每次批量删除的 children 数量（按 index 区间删）
CLEAR_PAGE_SIZE = int(os.environ.get("FEISHU_CLEAR_PAGE_SIZE", "200").strip() or "200")

if not APP_ID or not APP_SECRET or not DOCUMENT_ID or not LOCAL_MD_PATH:
    raise RuntimeError("feishu.env 缺少必要配置：FEISHU_APP_ID/FEISHU_APP_SECRET/FEISHU_DOCUMENT_ID/FEISHU_MD_PATH")

# ------------------------------
# HTTP：429/5xx 重试
# ------------------------------
MAX_RETRIES = 8
BASE_SLEEP = 0.8
JITTER = 0.3

def request_json(method: str, url: str, *, headers=None, params=None, json_body=None, hint="request") -> Dict:
    headers = headers or {}
    params = params or {}

    for attempt in range(MAX_RETRIES):
        resp = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=120)

        if resp.status_code == 429 or 500 <= resp.status_code <= 599:
            sleep_s = BASE_SLEEP * (2 ** attempt) + random.random() * JITTER
            ra = resp.headers.get("Retry-After")
            if ra:
                try:
                    sleep_s = max(sleep_s, float(ra))
                except Exception:
                    pass
            time.sleep(sleep_s)
            continue

        try:
            data = resp.json()
        except Exception:
            raise RuntimeError(
                f"{hint} 返回非 JSON，HTTP {resp.status_code}\n"
                f"method={method} url={url}\n"
                f"resp={(resp.text or '')[:800]}"
            )

        return data

    raise RuntimeError(f"{hint} 重试次数耗尽")

# ------------------------------
# Token
# ------------------------------
def get_tenant_access_token() -> str:
    url = f"{FEISHU_OPENAPI_BASE}/auth/v3/tenant_access_token/internal"
    data = request_json("POST", url, json_body={"app_id": APP_ID, "app_secret": APP_SECRET}, hint="tenant_access_token")
    if data.get("code") != 0:
        raise RuntimeError(f"获取 tenant_access_token 失败: {data}")
    return data["tenant_access_token"]

# ------------------------------
# Doc 元信息：读取标题 / 更新标题
# ------------------------------
def get_document_meta(document_id: str, token: str) -> Dict[str, Any]:
    url = f"{FEISHU_OPENAPI_BASE}/docx/v1/documents/{document_id}"
    headers = {"Authorization": f"Bearer {token}"}
    data = request_json("GET", url, headers=headers, hint="get_document_meta")
    if data.get("code") != 0:
        raise RuntimeError(f"读取文档 meta 失败: {data}")
    return data.get("data") or {}

def update_document_title(document_id: str, token: str, title: str) -> None:
    url = f"{FEISHU_OPENAPI_BASE}/docx/v1/documents/{document_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
    data = request_json("PATCH", url, headers=headers, json_body={"title": title}, hint="update_document_title")
    if data.get("code") != 0:
        raise RuntimeError(f"更新文档标题失败: {data}")

# ------------------------------
# Convert
# ------------------------------
def convert_markdown(md: str, token: str) -> Dict[str, Any]:
    url = f"{FEISHU_OPENAPI_BASE}/docx/v1/documents/blocks/convert"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
    payload = {"content_type": "markdown", "content": md}
    data = request_json("POST", url, headers=headers, json_body=payload, hint="convert")
    if data.get("code") != 0:
        raise RuntimeError(f"convert 失败: {data}")
    return data.get("data") or {}

# ------------------------------
# 顺序 & 块池提取（核心：优先 first_level_block_ids）
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
# 清洗
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
        # 兼容 unordered/bullet 字段
        if bt == 12 and "unordered" in obj and "bullet" not in obj:
            obj["bullet"] = obj.pop("unordered")

        for k, v in list(obj.items()):
            obj[k] = sanitize(v)
        return obj

    if isinstance(obj, list):
        return [sanitize(x) for x in obj]

    return obj

# ------------------------------
# children 获取 / 清空正文（按 index 区间删除）
# ------------------------------
def get_children_first_page(document_id: str, block_id: str, token: str, page_size: int = 200) -> List[str]:
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{FEISHU_OPENAPI_BASE}/docx/v1/documents/{document_id}/blocks/{block_id}/children"
    params = {"page_size": page_size}

    data = request_json("GET", url, headers=headers, params=params, hint="get_children_first_page")
    if data.get("code") != 0:
        raise RuntimeError(f"获取 children 失败: {data}")

    items = data.get("data", {}).get("items") or []
    return [it.get("block_id") for it in items if it.get("block_id")]

def batch_delete_children_by_index(document_id: str, block_id: str, token: str, start_index: int, end_index: int) -> None:
    """
    注意：这个接口是 DELETE，并且参数是 start_index / end_index
    end_index 通常是“开区间”，即删除 [start_index, end_index)。
    """
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
    url = f"{FEISHU_OPENAPI_BASE}/docx/v1/documents/{document_id}/blocks/{block_id}/children/batch_delete"
    payload = {"start_index": start_index, "end_index": end_index}

    data = request_json("DELETE", url, headers=headers, params={}, json_body=payload, hint="batch_delete")
    if data.get("code") != 0:
        raise RuntimeError(f"batch_delete 失败: {data}")

def clear_document_body_keep_title(document_id: str, token: str) -> None:
    """
    1) 读取标题
    2) 删除根块下所有 children（循环按 index 区间删）
    3) 把标题写回去（强保证“不修改标题”）
    """
    meta = get_document_meta(document_id, token)
    title = meta.get("title") or ""

    # 根块（Page block）通常就是 document_id
    body_root = document_id

    # 循环删：每次删掉“第一页 children”，始终从 index=0 开始删
    while True:
        ids = get_children_first_page(document_id, body_root, token, page_size=CLEAR_PAGE_SIZE)
        if not ids:
            break
        batch_delete_children_by_index(document_id, body_root, token, start_index=0, end_index=len(ids))
        time.sleep(0.15)

    if title:
        update_document_title(document_id, token, title)

# ------------------------------
# 分段：按 H2 / H3
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
# 写入：descendant
# ------------------------------
def insert_descendant(
    document_id: str,
    parent_block_id: str,
    token: str,
    children_id: List[str],
    descendants: List[Dict[str, Any]],
    index: int
) -> Dict[str, Any]:
    url = f"{FEISHU_OPENAPI_BASE}/docx/v1/documents/{document_id}/blocks/{parent_block_id}/descendant"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}

    # 这里先不带 document_revision_id，避免某些租户/接口对 -1 不友好
    params = {}
    payload = {"children_id": children_id, "descendants": descendants, "index": index}
    return request_json("POST", url, headers=headers, params=params, json_body=payload, hint="descendant_insert")

def is_too_many_descendants_error(resp: Dict[str, Any]) -> bool:
    try:
        err = resp.get("error") or {}
        fvs = err.get("field_violations") or []
        for fv in fvs:
            if fv.get("field") == "descendants" and "max len" in (fv.get("description") or "") and "1000" in (fv.get("description") or ""):
                return True
    except Exception:
        pass
    msg = (resp.get("msg") or "").lower()
    return ("max len" in msg and "1000" in msg)

# ------------------------------
# 单段：convert -> 闭合子树 -> insert
# ------------------------------
def sync_one_chunk(
    md_chunk: str,
    title: str,
    document_id: str,
    parent_block_id: str,
    token: str,
    index: int
) -> Tuple[bool, int, Dict[str, Any]]:
    cdata = convert_markdown(md_chunk, token)
    order_ids, pool = extract_order_and_pool(cdata)

    pool = sanitize(pool)
    block_map = build_block_map(pool)

    descendants: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for rid in order_ids:
        subtree = collect_subtree(block_map, rid)
        for b in subtree:
            bid = b.get("block_id")
            if bid and bid not in seen:
                seen.add(bid)
                descendants.append(b)

    if len(descendants) > MAX_DESCENDANTS:
        resp = {
            "code": 99992402,
            "msg": "field validation failed",
            "error": {"field_violations": [{"field": "descendants", "description": f"the max len is {MAX_DESCENDANTS}"}]},
        }
        return False, index, resp

    resp = insert_descendant(document_id, parent_block_id, token, order_ids, descendants, index)
    if resp.get("code") != 0:
        return False, index, resp

    return True, index + len(order_ids), resp

# ------------------------------
# 主流程：每次先清空正文 + 保留标题，再同步
# ------------------------------
def sync():
    with open(LOCAL_MD_PATH, "r", encoding="utf-8") as f:
        md = f.read()

    token = get_tenant_access_token()
    print("[INFO] token OK")

    if ALWAYS_CLEAR_BEFORE_SYNC:
        print("[INFO] 清空文档正文（保留标题）...")
        clear_document_body_keep_title(DOCUMENT_ID, token)
        print("[INFO] 清空完成")

    # 写入位置：默认写到根块(DOCUMENT_ID)，也可用 env 指定 PARENT_BLOCK_ID
    parent = PARENT_BLOCK_ID or DOCUMENT_ID
    index = 0
    print(f"[INFO] parent_block_id = {parent}, index 从 {index} 开始写入")

    h2_sections = split_by_heading(md, level=2)
    print(f"[INFO] 共 {len(h2_sections)} 个二级段（##）")

    pbar = tqdm(total=len(h2_sections), desc="Sync sections", unit="sec")

    for h2_title, h2_md in h2_sections:
        ok, new_index, resp = sync_one_chunk(h2_md, h2_title, DOCUMENT_ID, parent, token, index)

        if ok:
            index = new_index
            pbar.update(1)
            time.sleep(0.12)
            continue

        # 超过 1000 descendants：二级段降级为三级段同步
        if is_too_many_descendants_error(resp):
            h3_sections = split_by_heading(h2_md, level=3)

            if len(h3_sections) > 1:
                pbar.total += (len(h3_sections) - 1)
                pbar.refresh()

            for h3_title, h3_md in h3_sections:
                ok3, new_index3, resp3 = sync_one_chunk(
                    h3_md,
                    f"{h2_title} / {h3_title}",
                    DOCUMENT_ID,
                    parent,
                    token,
                    index
                )
                if not ok3:
                    raise RuntimeError(f"[FAIL] H3 段写入失败 title={h2_title} / {h3_title} resp={resp3}")
                index = new_index3
                pbar.update(1)
                time.sleep(0.12)
            continue

        raise RuntimeError(f"[FAIL] 段写入失败 title={h2_title} resp={resp}")

    pbar.close()
    print("[DONE] 同步完成（每次先清空正文，标题保持不变）")

if __name__ == "__main__":
    sync()
