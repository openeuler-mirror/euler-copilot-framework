#!/bin/bash
set -euo pipefail

# 定义颜色代码
RED='\e[31m'
GREEN='\e[32m'
YELLOW='\e[33m'
BLUE='\e[34m'
MAGENTA='\e[35m'
CYAN='\e[36m'
RESET='\e[0m'

# 初始化全局变量
OS_ID=""
ARCH=""
OLLAMA_BIN_PATH="/usr/local/bin/ollama"
SERVICE_FILE="/etc/systemd/system/ollama.service"

# 带时间戳的输出函数
log() {
  local level=$1
  shift
  local color
  case "$level" in
    "INFO") color=${BLUE} ;;
    "SUCCESS") color=${GREEN} ;;
    "WARNING") color=${YELLOW} ;;
    "ERROR") color=${RED} ;;
    *) color=${RESET} ;;
  esac
  echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] $level: $*${RESET}"
}

# 操作系统检测
detect_os() {
  log "INFO" "步骤1/8：检测操作系统和架构..."
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID="${ID}"
    log "INFO" "检测到操作系统: ${PRETTY_NAME}"
  else
    log "ERROR" "无法检测操作系统类型"
    exit 1
  fi

  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64)  ARCH="amd64" ;;
    aarch64) ARCH="arm64" ;;
    armv7l)  ARCH="armv7" ;;
    *)       log "ERROR" "不支持的架构: $ARCH"; exit 1 ;;
  esac
  log "INFO" "系统架构: $ARCH"
}

# 安装系统依赖
install_dependencies() {
  log "INFO" "步骤2/8：安装系统依赖..."
  local deps=(curl wget tar gzip jq)

  case "$OS_ID" in
    ubuntu|debian)
      if ! apt-get update; then
        log "ERROR" "APT源更新失败"
        exit 1
      fi
      if ! DEBIAN_FRONTEND=noninteractive apt-get install -y "${deps[@]}"; then
        log "ERROR" "APT依赖安装失败"
        exit 1
      fi
      ;;
    centos|rhel|fedora|openEuler)
      if ! yum install -y "${deps[@]}"; then
        log "ERROR" "YUM依赖安装失败"
        exit 1
      fi
      ;;
    *)
      log "ERROR" "不支持的发行版: $OS_ID"
      exit 1
      ;;
  esac
  log "SUCCESS" "系统依赖安装完成"
}

# 获取Ollama下载地址
get_ollama_url() {
  local version="2025.0330"
  echo "https://repo.oepkgs.net/openEuler/rpm/openEuler-24.03-LTS/contrib/oedp/$version/ollama-linux-$ARCH.tgz"
}

# 安装Ollama核心
install_ollama() {
  log "INFO" "步骤3/8：安装Ollama核心..."
  local install_url=$(get_ollama_url)
  local tmp_file="/tmp/ollama-${ARCH}.tgz"

  if [ -x "$OLLAMA_BIN_PATH" ]; then
    log "WARNING" "发现已存在的Ollama安装，版本: $($OLLAMA_BIN_PATH --version)"
    read -p "是否重新安装？[y/N] " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || return 0
  fi

  log "INFO" "下载安装包: $install_url"
  if ! wget --show-progress -q -O "$tmp_file" "$install_url"; then
    log "ERROR" "下载失败，请检查：\n1.网络连接\n2.URL有效性: $install_url"
    exit 1
  fi

  log "INFO" "解压文件到系统目录"
  if ! tar -xzf "$tmp_file" -C "${OLLAMA_BIN_PATH%/*}"; then
    log "ERROR" "解压失败，可能原因：\n1.文件损坏\n2.磁盘空间不足\n3.权限问题"
    exit 1
  fi

  chmod +x "$OLLAMA_BIN_PATH"
  rm -f "$tmp_file"
  log "SUCCESS" "Ollama核心安装完成，版本: $($OLLAMA_BIN_PATH --version)"
}

# 修复用户配置
fix_user() {
  log "INFO" "步骤4/8: 修复用户配置..."
  # 清理旧用户
  if id ollama &>/dev/null; then
    userdel ollama
    log "INFO" "已删除旧ollama用户"
  fi

  # 创建正确配置的用户
  useradd -r -m -d /var/lib/ollama -s /bin/false ollama || {
    log "ERROR" "用户创建失败"
    exit 1
  }

  # 设置目录权限
  chown -R ollama:ollama /var/lib/ollama
  chmod 700 /var/lib/ollama
  log "SUCCESS" "用户配置修复完成"
}

# 服务配置
fix_service() {
  log "INFO" "步骤5/8：配置系统服务..."
  cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
Environment="OLLAMA_MODELS=/var/lib/ollama/.ollama/models"
Environment="OLLAMA_HOST=0.0.0.0:11434"
ExecStart=$OLLAMA_BIN_PATH serve
User=ollama
Group=ollama
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  log "SUCCESS" "服务配置更新完成"
}

# 清理并重启服务
restart_service() {
  log "INFO" "步骤6/8: 重启服务..."
  systemctl stop ollama || true
  rm -rf /var/lib/ollama/.ollama
  systemctl start ollama
  log "SUCCESS" "服务重启完成"
}

# 服务健康检查
health_check() {
  log "INFO" "步骤7/8：执行健康检查..."
  local retries=3
  local timeout=5

  # 启动服务
  if ! systemctl is-active ollama &>/dev/null; then
    systemctl enable --now ollama || {
      log "ERROR" "服务启动失败"
      journalctl -u ollama -n 20 --no-pager
      exit 1
    }
  fi

  # 等待服务就绪
  for i in $(seq 1 $retries); do
    if curl -s http://localhost:11434 &>/dev/null; then
      log "SUCCESS" "服务健康检查通过"
      return 0
    fi
    log "WARNING" "等待服务响应 (尝试 $i/$retries)..."
    sleep $timeout
  done

  log "ERROR" "服务未响应，可能问题：\n1.端口冲突\n2.启动超时\n3.权限问题"
  journalctl -u ollama -n 50 --no-pager
  exit 1
}

# 最终验证
final_check() {
  log "INFO" "步骤8/8：执行最终验证..."
  if ! command -v ollama &>/dev/null; then
    log "ERROR" "Ollama未正确安装"
    exit 1
  fi

  if ! ollama list &>/dev/null; then
    log "ERROR" "服务连接失败，请检查：\n1.服务状态: systemctl status ollama\n2.端口监听: ss -tuln | grep 11434"
    exit 1
  fi

  log "SUCCESS" "验证通过，您可以执行以下操作：\n  ollama list          # 查看模型列表\n  ollama run llama2    # 运行示例模型"
}

### 主执行流程 ###
main() {
  # 权限检查
  if [[ $EUID -ne 0 ]]; then
    log "ERROR" "请使用sudo运行此脚本"
    exit 1
  fi

  detect_os
  install_dependencies
  install_ollama
  fix_user
  fix_service
  restart_service
  health_check
  final_check
}

main
