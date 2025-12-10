#!/usr/bin/env bash
set -euo pipefail

# =========================
# 0. 日志初始化
# =========================
LOG_FILE="/var/log/doris_install_wsl_$(date +%Y%m%d_%H%M%S).log"
mkdir -p /var/log
touch "$LOG_FILE"
chmod 644 "$LOG_FILE"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "[$(date)] ===== Apache Doris on WSL Installer Started ====="

# =========================
# 1. 权限 & 环境检查
# =========================
if [ "$(id -u)" -ne 0 ]; then
  echo "[ERROR] 请用 root 运行本脚本，例如：sudo bash $0"
  exit 1
fi

if grep -qi microsoft /proc/version; then
  echo "[INFO] 检测到 WSL 环境。"
else
  echo "[WARN] 当前环境看起来不是 WSL（/proc/version 中未检测到 microsoft），继续安装但可能不是你期望的环境。"
fi

# Doris 启动脚本会拒绝带代理环境，先统一清掉
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY

# =========================
# 2. 版本 & 架构检测
# =========================
DORIS_VERSION="${DORIS_VERSION:-3.0.8}"   # 如需其它版本，可在执行脚本前 export DORIS_VERSION=3.1.3
ARCH="$(uname -m)"
DORIS_ARCH=""

case "$ARCH" in
  x86_64)
    if grep -q avx2 /proc/cpuinfo; then
      DORIS_ARCH="x64"
      echo "[INFO] x86_64 且支持 AVX2，使用 x64 二进制包。"
    else
      DORIS_ARCH="x64-noavx2"
      echo "[WARN] CPU 不支持 AVX2，使用 x64-noavx2 二进制包。"
    fi
    ;;
  aarch64)
    DORIS_ARCH="arm64"
    echo "[INFO] 检测到 aarch64，使用 arm64 二进制包。"
    ;;
  *)
    echo "[ERROR] 不支持的架构: $ARCH"
    exit 1
    ;;
esac

DORIS_PACKAGE="apache-doris-${DORIS_VERSION}-bin-${DORIS_ARCH}.tar.gz"
DOWNLOAD_URL="${DOWNLOAD_URL:-https://apache-doris-releases.oss-accelerate.aliyuncs.com/${DORIS_PACKAGE}}"

DORIS_BASE_DIR="/opt/apache-doris-${DORIS_VERSION}-bin-${DORIS_ARCH}"
DORIS_HOME="/opt/doris"

echo "[INFO] 准备安装 Doris 版本: ${DORIS_VERSION}, 架构: ${DORIS_ARCH}"
echo "[INFO] 下载地址: ${DOWNLOAD_URL}"
echo "[INFO] 安装目录: ${DORIS_BASE_DIR}"
echo "[INFO] 固定软链接: ${DORIS_HOME}"

# 不建议把 Doris 装在 /mnt/ 下
if echo "$DORIS_BASE_DIR" | grep -q '^/mnt/'; then
  echo "[ERROR] 安装路径在 /mnt/* 下会严重影响性能并可能踩各种坑，请改为 /opt 或 /home 下。"
  exit 1
fi

# =========================
# 3. 安装依赖（JDK 17 等）
# =========================
export DEBIAN_FRONTEND=noninteractive

echo "[INFO] 运行 apt-get update ..."
apt-get update -y

echo "[INFO] 安装依赖: ca-certificates wget tar openjdk-17-jdk python3 procps ..."
apt-get install -y ca-certificates wget tar openjdk-17-jdk python3 procps

JAVA_BIN="$(command -v java || true)"
if [ -z "$JAVA_BIN" ]; then
  echo "[ERROR] 安装 openjdk-17-jdk 后仍未找到 java，可手动检查。"
  exit 1
fi
JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$JAVA_BIN")")")"
echo "[INFO] 检测到 JAVA_HOME=${JAVA_HOME}"

# =========================
# 4. 创建 doris 用户 & 资源限制
# =========================
if ! id -u doris >/dev/null 2>&1; then
  echo "[INFO] 创建专用用户 doris ..."
  groupadd --system doris || true
  useradd --system --gid doris --home-dir /opt/doris --shell /bin/bash doris || true
else
  echo "[INFO] 用户 doris 已存在，跳过创建。"
fi

# ulimit: 最大文件句柄数
if ! grep -q '^doris[[:space:]]\+soft[[:space:]]\+nofile' /etc/security/limits.conf 2>/dev/null; then
  echo "[INFO] 在 /etc/security/limits.conf 中为 doris 配置 nofile 限制 ..."
  cat << 'EOF_LIMITS' >> /etc/security/limits.conf

# For Apache Doris
doris soft nofile 1000000
doris hard nofile 1000000
EOF_LIMITS
else
  echo "[INFO] /etc/security/limits.conf 中已包含 doris 的 nofile 配置，跳过。"
fi

# vm.max_map_count
SYSCTL_CONF="/etc/sysctl.d/99-doris.conf"
if [ ! -f "$SYSCTL_CONF" ]; then
  echo "[INFO] 创建 $SYSCTL_CONF 设置 vm.max_map_count=2000000 ..."
  echo "vm.max_map_count=2000000" > "$SYSCTL_CONF"
else
  if ! grep -q 'vm.max_map_count' "$SYSCTL_CONF"; then
    echo "[INFO] 向 $SYSCTL_CONF 追加 vm.max_map_count=2000000 ..."
    echo "vm.max_map_count=2000000" >> "$SYSCTL_CONF"
  else
    echo "[INFO] $SYSCTL_CONF 已包含 vm.max_map_count，跳过。"
  fi
fi
echo "[INFO] 应用 sysctl 配置（如失败仅提示，不中断脚本）..."
sysctl -p "$SYSCTL_CONF" || echo "[WARN] sysctl -p $SYSCTL_CONF 失败，请手动检查。"

# =========================
# 5. 下载 & 解压 Doris 二进制包
# =========================
mkdir -p /opt
cd /opt

if [ ! -f "$DORIS_PACKAGE" ]; then
  echo "[INFO] 未找到本地包 $DORIS_PACKAGE，开始下载 ..."
  if ! wget -O "$DORIS_PACKAGE" "$DOWNLOAD_URL"; then
    echo "[ERROR] 下载 Doris 安装包失败，请检查网络或手动下载到 /opt 再重试。"
    exit 1
  fi
else
  echo "[INFO] 已存在 /opt/$DORIS_PACKAGE，跳过下载。"
fi

if [ -d "$DORIS_BASE_DIR" ]; then
  echo "[INFO] 目录 $DORIS_BASE_DIR 已存在，将复用该目录（不覆盖）。"
else
  echo "[INFO] 解压 $DORIS_PACKAGE 到 /opt ..."
  tar -xzf "$DORIS_PACKAGE"
  # 推测解压出来的目录名，并重命名为 DORIS_BASE_DIR
  EXTRACTED_DIR="$(tar -tzf "$DORIS_PACKAGE" | head -1 | cut -f1 -d"/")"
  if [ -d "/opt/$EXTRACTED_DIR" ] && [ "/opt/$EXTRACTED_DIR" != "$DORIS_BASE_DIR" ]; then
    mv "/opt/$EXTRACTED_DIR" "$DORIS_BASE_DIR"
  fi
fi

# 建立固定软链接 /opt/doris
ln -sfn "$DORIS_BASE_DIR" "$DORIS_HOME"

echo "[INFO] 调整 Doris 目录权限为 doris:doris ..."
chown -R doris:doris "$DORIS_BASE_DIR"
chown -h doris:doris "$DORIS_HOME"

# =========================
# 6. 修改 Doris 配置 (fe.conf / be.conf)
# =========================
FE_CONF="${DORIS_HOME}/fe/conf/fe.conf"
BE_CONF="${DORIS_HOME}/be/conf/be.conf"

if [ ! -f "$FE_CONF" ] || [ ! -f "$BE_CONF" ]; then
  echo "[ERROR] 未找到 fe.conf 或 be.conf，请检查 ${DORIS_HOME}/fe/conf 和 ${DORIS_HOME}/be/conf。"
  exit 1
fi

echo "[INFO] 更新 fe.conf 和 be.conf 的 JAVA_HOME 与 priority_networks ..."

for CONF in "$FE_CONF" "$BE_CONF"; do
  # JAVA_HOME
  if grep -q '^JAVA_HOME=' "$CONF"; then
    sed -i "s|^JAVA_HOME=.*|JAVA_HOME=${JAVA_HOME}|" "$CONF"
  else
    echo "JAVA_HOME=${JAVA_HOME}" >> "$CONF"
  fi

  # 在 WSL 单机上用 127.0.0.1/32，避免多网卡/WSL 虚拟网卡选错
  if grep -q '^priority_networks=' "$CONF"; then
    sed -i "s|^priority_networks=.*|priority_networks=127.0.0.1/32|" "$CONF"
  else
    echo "priority_networks=127.0.0.1/32" >> "$CONF"
  fi
done

# =========================
# 7. WSL 专用补丁：禁用 BE 启动脚本中的 swap 检查
# =========================
BE_START="${DORIS_HOME}/be/bin/start_be.sh"

if [ -f "$BE_START" ]; then
  if grep -qi microsoft /proc/version; then
    echo "[INFO] 检测到 WSL 环境，尝试对 ${BE_START} 应用 swap 检查补丁 ..."
    if grep -q "Disable swap memory before starting be" "$BE_START"; then
      TS="$(date +%Y%m%d_%H%M%S)"
      cp "$BE_START" "${BE_START}.bak.${TS}"
      echo "[INFO] 已备份原始 start_be.sh 为 ${BE_START}.bak.${TS}"

      # 替换提示信息
      sed -i 's/Disable swap memory before starting be/Swap is enabled but ignored in WSL (patched by install_doris_wsl.sh)/' "$BE_START"

      # 在这行之后的若干行中，把 exit 1 注释掉
      sed -i '/Swap is enabled but ignored in WSL (patched by install_doris_wsl.sh)/,+3 s/^\([[:space:]]*\)exit 1/# \1exit 1  # ignored in WSL/' "$BE_START"

      echo "[INFO] 已在 WSL 中禁用 BE 启动脚本的 swap 检查。"
    else
      echo "[WARN] 未在 ${BE_START} 中找到 swap 检查提示字符串，可能该 Doris 版本脚本逻辑已变，如仍报 swap 相关错误请手动检查此脚本。"
    fi
  fi
else
  echo "[WARN] 未找到 ${BE_START}，稍后如 BE 无法启动请检查 Doris 安装目录结构。"
fi

# =========================
# 8. 配置 /etc/wsl.conf 以启用 systemd（下次 WSL 启动生效）
# =========================
if [ ! -f /etc/wsl.conf ]; then
  echo "[INFO] /etc/wsl.conf 不存在，创建并启用 systemd=true ..."
  cat << 'EOF_WSLCONF' > /etc/wsl.conf
[boot]
systemd=true
EOF_WSLCONF
  echo "[INFO] 已写入 /etc/wsl.conf。要让 systemd 生效，请在 Windows PowerShell 中执行： wsl --shutdown"
else
  if grep -q 'systemd=true' /etc/wsl.conf; then
    echo "[INFO] /etc/wsl.conf 已启用 systemd=true。"
  else
    echo "[WARN] /etc/wsl.conf 已存在但未检测到 systemd=true。"
    echo "       建议手动编辑 /etc/wsl.conf，加入："
    echo "       [boot]"
    echo "       systemd=true"
  fi
fi

# =========================
# 9. 生成 systemd Unit (doris-fe / doris-be)
# =========================
FE_SERVICE="/etc/systemd/system/doris-fe.service"
BE_SERVICE="/etc/systemd/system/doris-be.service"

echo "[INFO] 创建 systemd 单元文件: $FE_SERVICE"
cat > "$FE_SERVICE" << EOF_FE
[Unit]
Description=Apache Doris Frontend (FE)
After=network.target

[Service]
Type=forking
User=doris
Group=doris
WorkingDirectory=${DORIS_HOME}
Environment=JAVA_HOME=${JAVA_HOME}
Environment=DORIS_HOME=${DORIS_HOME}
Environment=http_proxy=
Environment=https_proxy=
Environment=HTTP_PROXY=
Environment=HTTPS_PROXY=
LimitNOFILE=1000000
ExecStart=${DORIS_HOME}/fe/bin/start_fe.sh --daemon
ExecStop=${DORIS_HOME}/fe/bin/stop_fe.sh
PIDFile=${DORIS_HOME}/fe/bin/fe.pid
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF_FE

echo "[INFO] 创建 systemd 单元文件: $BE_SERVICE"
cat > "$BE_SERVICE" << EOF_BE
[Unit]
Description=Apache Doris Backend (BE)
After=network.target doris-fe.service
Requires=doris-fe.service

[Service]
Type=forking
User=doris
Group=doris
WorkingDirectory=${DORIS_HOME}
Environment=JAVA_HOME=${JAVA_HOME}
Environment=DORIS_HOME=${DORIS_HOME}
Environment=http_proxy=
Environment=https_proxy=
Environment=HTTP_PROXY=
Environment=HTTPS_PROXY=
LimitNOFILE=1000000
ExecStart=${DORIS_HOME}/be/bin/start_be.sh --daemon
ExecStop=${DORIS_HOME}/be/bin/stop_be.sh
PIDFile=${DORIS_HOME}/be/bin/be.pid
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF_BE

chmod 644 "$FE_SERVICE" "$BE_SERVICE"

# =========================
# 10. 检测当前是否已由 systemd 管理 (WSL 新版才支持)
# =========================
IS_SYSTEMD=0
if command -v systemctl >/dev/null 2>&1; then
  INIT_COMM="$(ps -p 1 -o comm= || true)"
  if [ "$INIT_COMM" = "systemd" ]; then
    IS_SYSTEMD=1
  fi
fi

if [ "$IS_SYSTEMD" -eq 1 ]; then
  echo "[INFO] 检测到当前 WSL 已由 systemd 管理 (PID 1 = systemd)，直接启用并启动服务。"
  systemctl daemon-reload
  systemctl enable doris-fe.service doris-be.service

  echo "[INFO] 启动 Doris FE ..."
  systemctl restart doris-fe.service || {
    echo "[ERROR] systemctl restart doris-fe 失败，请查看：journalctl -u doris-fe -xe"
    exit 1
  }

  echo "[INFO] 启动 Doris BE ..."
  systemctl restart doris-be.service || {
    echo "[ERROR] systemctl restart doris-be 失败，请查看：journalctl -u doris-be -xe"
    exit 1
  }
else
  echo "[WARN] 当前 WSL 本次启动并未由 systemd 管理 (PID 1 != systemd)。"
  echo "[WARN] systemd unit 已创建，但要想让它随 WSL 启动自动运行，需要："
  echo "       1) 确保 /etc/wsl.conf 中 [boot] systemd=true"
  echo "       2) 在 Windows PowerShell 中执行： wsl --shutdown"
  echo "       3) 再次进入该 WSL，此时 systemd 会自动启用，doris-fe / doris-be 也会随之启动。"
  echo "[INFO] 当前会先以 doris 用户手动启动一次 FE/BE，方便你立即使用。"

  # 手动启动 FE & BE（清代理 + 注入 JAVA_HOME）
  su -s /bin/bash - doris -c "unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY; cd ${DORIS_HOME}/fe && ./bin/start_fe.sh --daemon"
  sleep 5
  su -s /bin/bash - doris -c "unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY; cd ${DORIS_HOME}/be && ./bin/start_be.sh --daemon"
fi

# =========================
# 11. 简单存活检查
# =========================
echo "[INFO] 简单检查 FE/BE 进程存活情况 ..."

if su -s /bin/bash - doris -c "cd ${DORIS_HOME}/fe && kill -0 \$(cat bin/fe.pid 2>/dev/null) 2>/dev/null"; then
  echo "[INFO] Doris FE 进程看起来正常运行。"
else
  echo "[WARN] Doris FE 进程检查失败，请查看 ${DORIS_HOME}/fe/log/fe.log。"
fi

if su -s /bin/bash - doris -c "cd ${DORIS_HOME}/be && kill -0 \$(cat bin/be.pid 2>/dev/null) 2>/dev/null"; then
  echo "[INFO] Doris BE 进程看起来正常运行。"
else
  echo "[WARN] Doris BE 进程检查失败，请查看 ${DORIS_HOME}/be/log/be.out 或 be.INFO。"
fi

echo "===================================================================="
echo "[INFO] Doris 安装脚本执行完成。"
echo "[INFO] 安装日志文件：${LOG_FILE}"
echo "[INFO] Doris 安装目录：${DORIS_HOME}"
echo "[INFO] FE 默认 MySQL 端口：9030, HTTP 端口：8030"
echo "[INFO] BE 默认端口：9060 等"
echo "[INFO] 你可以在 Windows 侧用任意 MySQL 客户端连接：host=127.0.0.1, port=9030, user=root, password=''"
echo "===================================================================="
