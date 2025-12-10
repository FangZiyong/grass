#!/usr/bin/env bash
set -u
set -o pipefail

DORIS_HOME="${DORIS_HOME:-/opt/doris}"
FE_HTTP_PORT="${FE_HTTP_PORT:-8030}"
FE_SQL_PORT="${FE_SQL_PORT:-9030}"
BE_WEBSERVER_PORT="${BE_WEBSERVER_PORT:-8040}"

EXIT_CODE=0

ok()   { echo "[OK]   $*"; }
warn() { echo "[WARN] $*"; }
fail() { echo "[FAIL] $*"; EXIT_CODE=1; }

echo "===== Doris WSL 自检开始 ====="
echo "DORIS_HOME=${DORIS_HOME}"
echo

# 1. 目录结构检查
if [ -d "${DORIS_HOME}/fe" ] && [ -d "${DORIS_HOME}/be" ]; then
  ok "找到 FE/BE 目录：${DORIS_HOME}/fe 和 ${DORIS_HOME}/be"
else
  fail "未找到 FE/BE 目录，请确认安装脚本是否成功执行，或 DORIS_HOME 是否为 ${DORIS_HOME}"
fi
echo

# 2. systemd 服务状态检查（如果 systemd 存在）
if command -v systemctl >/dev/null 2>&1; then
  INIT_COMM="$(ps -p 1 -o comm= 2>/dev/null || true)"
  if [ "$INIT_COMM" = "systemd" ]; then
    echo ">>> 检测到当前 WSL 已由 systemd 管理 (PID 1 = systemd)，检查服务状态 ..."
    if systemctl list-unit-files | grep -q '^doris-fe\.service'; then
      systemctl is-enabled doris-fe.service >/dev/null 2>&1 && \
        ok "doris-fe.service 已设置为开机自启" || \
        warn "doris-fe.service 未设置为开机自启"
      systemctl is-active doris-fe.service >/dev/null 2>&1 && \
        ok "doris-fe.service 当前处于运行状态" || \
        fail "doris-fe.service 未在运行，请 manual: systemctl status doris-fe"
    else
      warn "未找到 doris-fe.service，可能安装脚本没跑完或放在其他机器。"
    fi

    if systemctl list-unit-files | grep -q '^doris-be\.service'; then
      systemctl is-enabled doris-be.service >/dev/null 2>&1 && \
        ok "doris-be.service 已设置为开机自启" || \
        warn "doris-be.service 未设置为开机自启"
      systemctl is-active doris-be.service >/dev/null 2>&1 && \
        ok "doris-be.service 当前处于运行状态" || \
        fail "doris-be.service 未在运行，请 manual: systemctl status doris-be"
    else
      warn "未找到 doris-be.service，可能安装脚本没跑完或放在其他机器。"
    fi
  else
    warn "当前 PID1 非 systemd (${INIT_COMM:-unknown})，本次启动不会由 systemd 自动拉起 Doris。"
    echo "      你可以在 Windows PowerShell 里执行：wsl --shutdown，然后重新进入该 WSL 以启用 systemd。"
  fi
else
  warn "systemctl 不存在，说明当前环境没有 systemd 或未启用。"
fi
echo

# 3. 进程 & PID 文件检测
FE_PID_FILE="${DORIS_HOME}/fe/bin/fe.pid"
BE_PID_FILE="${DORIS_HOME}/be/bin/be.pid"

if [ -f "$FE_PID_FILE" ]; then
  FE_PID="$(cat "$FE_PID_FILE" 2>/dev/null || echo "")"
  if [ -n "$FE_PID" ] && kill -0 "$FE_PID" 2>/dev/null; then
    ok "通过 fe.pid(${FE_PID}) 检测到 FE 进程存活"
  else
    fail "fe.pid 存在但进程不在运行，请检查 FE 日志：${DORIS_HOME}/fe/log/fe.log"
  fi
else
  warn "未发现 ${FE_PID_FILE}，FE 可能未成功启动或 PID 文件路径不同。"
fi

if [ -f "$BE_PID_FILE" ]; then
  BE_PID="$(cat "$BE_PID_FILE" 2>/dev/null || echo "")"
  if [ -n "$BE_PID" ] && kill -0 "$BE_PID" 2>/dev/null; then
    ok "通过 be.pid(${BE_PID}) 检测到 BE 进程存活"
  else
    fail "be.pid 存在但进程不在运行，请检查 BE 日志：${DORIS_HOME}/be/log/be.out 或 be.INFO"
  fi
else
  warn "未发现 ${BE_PID_FILE}，BE 可能未成功启动或 PID 文件路径不同。"
fi
echo

# 4. 端口监听检查
if command -v ss >/dev/null 2>&1; then
  echo ">>> 检查 Doris 常用端口监听 (FE: 9030/8030, BE: 9060/8040 等) ..."
  ss -lntp | grep -E ':(9030|8030|9060|8040)\b' || warn "未在 ss 输出中发现 9030/8030/9060/8040 端口监听，请确认 FE/BE 是否已启动。"
else
  warn "未找到 ss 命令，跳过端口检查。"
fi
echo

# 5. FE HTTP /api/health 健康检查
# 官方文档：GET /api/health 会返回存活 BE 数等信息，HTTP 200 即正常 :contentReference[oaicite:0]{index=0}
if command -v curl >/dev/null 2>&1; then
  echo ">>> 调用 FE 健康检查接口：http://127.0.0.1:${FE_HTTP_PORT}/api/health"
  HTTP_CODE="$(curl -sS -o /tmp/doris_fe_health.$$.json -w '%{http_code}' "http://127.0.0.1:${FE_HTTP_PORT}/api/health" || echo "000")"
  if [ "$HTTP_CODE" = "200" ]; then
    ok "FE /api/health 返回 200，基本可认为 FE 正常对外提供 HTTP 服务。"
    echo "[DEBUG] FE /api/health 响应："
    cat /tmp/doris_fe_health.$$.json
    echo
  else
    fail "FE /api/health HTTP 状态码为 ${HTTP_CODE}，请检查 FE 是否成功启动或端口是否被占用。"
  fi
  rm -f /tmp/doris_fe_health.$$.json
else
  warn "未安装 curl，跳过 HTTP 健康检查。可 apt-get install curl 后重试本脚本。"
fi
echo

# 6. MySQL 协议连通性检查（默认 9030）:contentReference[oaicite:1]{index=1}
if command -v mysql >/dev/null 2>&1; then
  echo ">>> 使用 mysql 客户端连接 FE query_port=${FE_SQL_PORT} 做简单 SQL 测试 ..."
  if mysql -h 127.0.0.1 -P"${FE_SQL_PORT}" -uroot -e "SELECT 'doris_ok' AS ping;" >/tmp/doris_mysql_ping.$$.log 2>&1; then
    ok "MySQL 协议连接成功，能在 127.0.0.1:${FE_SQL_PORT} 通过 root 访问。"
    cat /tmp/doris_mysql_ping.$$.log
    echo
    echo ">>> 进一步查看 FE / BE 注册情况 ..."
    mysql -h 127.0.0.1 -P"${FE_SQL_PORT}" -uroot -e "SHOW FRONTENDS\G; SHOW BACKENDS\G; SHOW DATABASES;"
  else
    fail "mysql 客户端连接 127.0.0.1:${FE_SQL_PORT} 失败，日志："
    cat /tmp/doris_mysql_ping.$$.log
    echo
    echo "   * 请确认 FE 是否监听 9030 端口"
    echo "   * 如报 'Access denied for user'，说明 Doris 已开启密码，请按实际账号重试"
  fi
  rm -f /tmp/doris_mysql_ping.$$.log
else
  warn "未安装 mysql 客户端，无法做 SQL 层验证。建议：sudo apt-get install -y mysql-client 后重新运行本脚本。"
fi

echo
echo "===== Doris WSL 自检结束，整体结果：EXIT_CODE=${EXIT_CODE} ====="
exit "$EXIT_CODE"
