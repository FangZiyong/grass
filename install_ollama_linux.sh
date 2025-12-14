#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash install_ollama_linux.sh                 # install + start + verify
#   bash install_ollama_linux.sh qwen2.5:7b-instruct qwen3:30b  # also pull models
#
# Optional:
#   OLLAMA_VERSION=0.5.7 bash install_ollama_linux.sh
# (官方支持用 OLLAMA_VERSION 指定版本) :contentReference[oaicite:1]{index=1}

RED="$(tput setaf 1 2>/dev/null || true)"
GRN="$(tput setaf 2 2>/dev/null || true)"
YEL="$(tput setaf 3 2>/dev/null || true)"
RST="$(tput sgr0 2>/dev/null || true)"

log()  { echo "${GRN}>>>${RST} $*"; }
warn() { echo "${YEL}>>>${RST} $*"; }
err()  { echo "${RED}ERROR:${RST} $*" >&2; exit 1; }

need_cmd() { command -v "$1" >/dev/null 2>&1; }

is_wsl2() {
  uname -r | grep -qiE 'microsoft.*wsl2|microsoft.*WSL2'
}

have_systemd_running() {
  need_cmd systemctl && systemctl is-system-running >/dev/null 2>&1
}

install_deps() {
  local pkgs=(curl awk grep sed tee xargs tar)

  # install.sh 本身会检查这些工具 :contentReference[oaicite:2]{index=2}
  local missing=()
  for p in "${pkgs[@]}"; do
    if ! need_cmd "$p"; then missing+=("$p"); fi
  done
  if [ ${#missing[@]} -eq 0 ]; then
    log "Dependencies already present."
    return
  fi

  log "Installing dependencies: ${missing[*]}"

  if need_cmd apt-get; then
    sudo apt-get update -y
    sudo apt-get install -y curl gawk grep sed coreutils tar
  elif need_cmd dnf; then
    sudo dnf install -y curl gawk grep sed coreutils tar
  elif need_cmd yum; then
    sudo yum install -y curl gawk grep sed coreutils tar
  elif need_cmd pacman; then
    sudo pacman -Syu --noconfirm curl gawk grep sed coreutils tar
  elif need_cmd zypper; then
    sudo zypper install -y curl gawk grep sed coreutils tar
  else
    err "No supported package manager found (apt/dnf/yum/pacman/zypper). Please install: curl awk grep sed tee xargs tar"
  fi
}

install_ollama() {
  log "Installing Ollama via official installer..."
  # 官方推荐命令 :contentReference[oaicite:3]{index=3}
  curl -fsSL https://ollama.com/install.sh | sh
}

start_ollama() {
  if have_systemd_running; then
    log "Starting Ollama systemd service..."
    sudo systemctl daemon-reload || true
    sudo systemctl enable ollama >/dev/null 2>&1 || true
    sudo systemctl restart ollama
    sudo systemctl --no-pager --full status ollama || true
  else
    # WSL2 常见情况：systemd 未启用。install.sh 会提示这一点。 :contentReference[oaicite:4]{index=4}
    warn "systemd is not running; starting 'ollama serve' in background (user session)."
    mkdir -p "${HOME}/.ollama"
    # 尽量避免重复启动
    if pgrep -f "ollama serve" >/dev/null 2>&1; then
      warn "ollama serve already running."
    else
      nohup ollama serve > "${HOME}/.ollama/serve.log" 2>&1 &
      disown || true
      log "Started: ollama serve (log: ${HOME}/.ollama/serve.log)"
    fi
  fi
}

verify_ollama() {
  log "Verifying Ollama CLI..."
  ollama -v

  log "Verifying Ollama API on 127.0.0.1:11434..."
  # install.sh 安装完成提示 API 在 127.0.0.1:11434 :contentReference[oaicite:5]{index=5}
  curl -fsSL http://127.0.0.1:11434/api/tags | head -c 400 || true
  echo
  log "OK."
}

pull_models() {
  if [ $# -eq 0 ]; then
    return
  fi
  log "Pulling models: $*"
  for m in "$@"; do
    ollama pull "$m"
  done
}

main() {
  [ "$(uname -s)" = "Linux" ] || err "This script is for Linux/WSL only."

  if is_wsl2; then
    log "WSL2 detected."
  fi

  install_deps
  install_ollama
  start_ollama
  verify_ollama
  pull_models "$@"

  log "Done. Try: ollama run qwen2.5:7b-instruct"
}

main "$@"
