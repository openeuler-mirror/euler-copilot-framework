#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2024-2026 openEuler SIG-Intelligence
#
# Witty MCP Manager 测试环境管理脚本
# 
# 适用环境: openEuler 24.03 LTS SP3 (或其他 Linux)
# 运行位置: 在 Linux 本地直接执行
#
# 前提条件:
#   - openEuler 24.03 LTS SP3 已配置
#   - MCP Server RPM 已安装 (可选，部分安装也兼容)
#   - 本仓库已克隆到本地
#   - 具有 root 权限或 sudo 权限
#
# 功能:
#   - 使用 uv 配置开发依赖
#   - 安装和配置守护进程
#   - 启动/停止/重启守护进程
#   - 清理配置文件和状态
#   - 查看日志和状态
#   - 测试 MCP 服务器 (发现/ping/tools/call)
#
# 使用方法:
#   cd /path/to/euler-copilot/framework/witty_mcp_manager
#   ./scripts/test_env.sh COMMAND [OPTIONS]
#
# 命令:
#   setup-dev          配置本地开发环境 (uv sync)
#   install            安装服务到系统
#   start              启动守护进程
#   stop               停止守护进程
#   restart            重启守护进程
#   status             检查守护进程状态
#   logs               查看守护进程日志
#   clean              清理配置和状态目录
#   clean-all          完全清理 (包括卸载服务)
#   test-mcps          测试 MCP 服务器 (发现/ping/tools/call)
#   health             健康检查
#   help               显示帮助信息

set -euo pipefail

# 脚本路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 默认配置
MCP_SERVERS_PATH="${MCP_SERVERS_PATH:-/opt/mcp-servers/servers}"
MCP_CENTER_PATH="${MCP_CENTER_PATH:-/usr/lib/sysagent/mcp_center/mcp_config}"
STATE_DIR="${STATE_DIR:-/var/lib/witty-mcp-manager}"
RUNTIME_DIR="${RUNTIME_DIR:-/run/witty}"
CONFIG_DIR="${CONFIG_DIR:-/etc/witty}"
SERVICE_NAME="witty-mcp-manager"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 辅助函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# 检查是否在项目根目录
check_project_root() {
    if [[ ! -f "${PROJECT_ROOT}/pyproject.toml" ]]; then
        log_error "未找到 pyproject.toml，请确保在 witty_mcp_manager 目录中运行此脚本"
        log_info "当前目录: $(pwd)"
        log_info "PROJECT_ROOT: ${PROJECT_ROOT}"
        exit 1
    fi
}

# 检查是否在 Linux 上运行
check_linux() {
    if [[ "$(uname -s)" != "Linux" ]]; then
        log_error "此脚本只能在 Linux 系统上运行"
        log_info "当前系统: $(uname -s)"
        exit 1
    fi
}

# 智能执行命令（root 用户直接执行，非 root 使用 sudo）
run_as_root() {
    if [[ $EUID -eq 0 ]]; then
        # 已是 root 用户，直接执行
        "$@"
    else
        # 非 root 用户，使用 sudo
        sudo "$@"
    fi
}

# ============================================
# 开发环境配置
# ============================================

setup_dev() {
    log_info "配置本地开发环境..."
    
    check_project_root
    
    # 检查 uv
    if ! command -v uv >/dev/null 2>&1; then
        log_error "uv 未安装。请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    
    log_info "使用 uv 同步依赖..."
    cd "${PROJECT_ROOT}"
    uv sync --all-extras
    
    log_success "开发环境配置完成"
    log_info "验证安装..."
    uv run python -c "import witty_mcp_manager; print(f'witty_mcp_manager 已安装')"
    
    log_info "可以运行以下命令验证代码质量:"
    echo "  uv run ruff format --check ."
    echo "  uv run ruff check ."
    echo "  uv run mypy src"
    echo "  uv run pytest -q"
}

# ============================================
# 安装服务
# ============================================

install_service() {
    log_info "安装 Witty MCP Manager 服务..."
    
    check_linux
    check_project_root
    
    # 创建 witty-mcp 用户
    if ! id witty-mcp >/dev/null 2>&1; then
        log_info "创建 witty-mcp 用户..."
        run_as_root useradd -r -s /sbin/nologin witty-mcp
    else
        log_info "witty-mcp 用户已存在"
    fi
    
    # 创建目录
    log_info "创建目录结构..."
    run_as_root mkdir -p ${CONFIG_DIR}
    run_as_root mkdir -p ${STATE_DIR}/{overrides/global,overrides/users,cache,runtime}
    run_as_root mkdir -p ${RUNTIME_DIR}
    
    # 设置权限
    log_info "设置目录权限..."
    run_as_root chown -R witty-mcp:witty-mcp ${STATE_DIR}
    run_as_root chown -R witty-mcp:witty-mcp ${RUNTIME_DIR}
    run_as_root chmod 755 ${RUNTIME_DIR}
    
    # 检查 /opt/mcp-servers 权限
    if [[ -d "${MCP_SERVERS_PATH}" ]]; then
        run_as_root chmod 755 ${MCP_SERVERS_PATH}
        local count=$(ls -1 ${MCP_SERVERS_PATH} 2>/dev/null | wc -l)
        log_success "MCP 服务器路径已配置: ${MCP_SERVERS_PATH} (${count} 个子目录)"
    else
        log_warn "MCP 服务器路径不存在: ${MCP_SERVERS_PATH}"
        log_info "如果需要测试 MCP，请先安装 MCP Server RPM 包"
    fi
    
    # 安装服务文件
    log_info "安装 systemd 服务..."
    if [[ ! -f "${PROJECT_ROOT}/data/witty-mcp-manager.service" ]]; then
        log_error "服务文件不存在: ${PROJECT_ROOT}/data/witty-mcp-manager.service"
        exit 1
    fi
    run_as_root cp ${PROJECT_ROOT}/data/witty-mcp-manager.service /usr/lib/systemd/system/
    run_as_root chmod 644 /usr/lib/systemd/system/witty-mcp-manager.service
    
    # 重载 systemd
    run_as_root systemctl daemon-reload
    
    # 启用服务
    run_as_root systemctl enable ${SERVICE_NAME}
    
    log_success "服务安装完成"
    log_info "使用以下命令管理服务:"
    echo "  ./scripts/test_env.sh start    # 启动服务"
    echo "  ./scripts/test_env.sh status   # 查看状态"
    echo "  ./scripts/test_env.sh logs     # 查看日志"
}

# ============================================
# 服务管理
# ============================================

start_service() {
    log_info "启动守护进程..."
    check_linux
    run_as_root systemctl start ${SERVICE_NAME}
    sleep 2
    check_status
}

stop_service() {
    log_info "停止守护进程..."
    check_linux
    run_as_root systemctl stop ${SERVICE_NAME}
    log_success "守护进程已停止"
}

restart_service() {
    log_info "重启守护进程..."
    check_linux
    run_as_root systemctl restart ${SERVICE_NAME}
    sleep 2
    check_status
}

check_status() {
    log_info "检查服务状态..."
    check_linux
    run_as_root systemctl status ${SERVICE_NAME} --no-pager || true
}

show_logs() {
    local lines="${1:-100}"
    local follow="${2:-}"
    
    check_linux
    log_info "查看日志 (最近 ${lines} 行)..."
    
    if [[ -n "${follow}" ]]; then
        run_as_root journalctl -u ${SERVICE_NAME} -n ${lines} -f
    else
        run_as_root journalctl -u ${SERVICE_NAME} -n ${lines} --no-pager
    fi
}

# ============================================
# 清理操作
# ============================================

clean_state() {
    log_warn "清理配置和状态目录..."
    
    read -p "确认清理 ${STATE_DIR}? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "取消清理操作"
        return
    fi
    
    check_linux
    
    # 停止服务
    if run_as_root systemctl is-active ${SERVICE_NAME} >/dev/null 2>&1; then
        log_info "停止服务..."
        run_as_root systemctl stop ${SERVICE_NAME}
    fi
    
    # 清理状态目录
    log_info "清理状态目录..."
    run_as_root rm -rf ${STATE_DIR}/overrides/*
    run_as_root rm -rf ${STATE_DIR}/cache/*
    run_as_root rm -rf ${STATE_DIR}/runtime/*
    
    # 清理运行时目录
    log_info "清理运行时目录..."
    run_as_root rm -f ${RUNTIME_DIR}/*
    
    # 重建目录结构
    run_as_root mkdir -p ${STATE_DIR}/{overrides/global,overrides/users,cache,runtime}
    
    # 恢复权限
    run_as_root chown -R witty-mcp:witty-mcp ${STATE_DIR}
    run_as_root chown -R witty-mcp:witty-mcp ${RUNTIME_DIR}
    
    log_success "清理完成"
}

clean_all() {
    log_warn "完全清理 (包括卸载服务)..."
    
    read -p "确认完全清理? 这将删除所有配置和服务。(y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "取消清理操作"
        return
    fi
    
    check_linux
    
    # 停止并禁用服务
    if run_as_root systemctl is-active ${SERVICE_NAME} >/dev/null 2>&1; then
        log_info "停止服务..."
        run_as_root systemctl stop ${SERVICE_NAME}
    fi
    
    if run_as_root systemctl is-enabled ${SERVICE_NAME} >/dev/null 2>&1; then
        log_info "禁用服务..."
        run_as_root systemctl disable ${SERVICE_NAME}
    fi
    
    # 删除服务文件
    if [[ -f /usr/lib/systemd/system/${SERVICE_NAME}.service ]]; then
        log_info "删除服务文件..."
        run_as_root rm -f /usr/lib/systemd/system/${SERVICE_NAME}.service
        run_as_root systemctl daemon-reload
    fi
    
    # 删除目录
    log_info "删除目录..."
    run_as_root rm -rf ${STATE_DIR}
    run_as_root rm -rf ${RUNTIME_DIR}
    run_as_root rm -rf ${CONFIG_DIR}
    
    log_success "完全清理完成"
    log_info "需要重新安装，请运行: ./scripts/test_env.sh install"
}

# ============================================
# MCP 测试
# ============================================

# UDS socket 路径
SOCK_PATH="${RUNTIME_DIR}/mcp-manager.sock"
# 默认测试用户
WITTY_USER="${WITTY_USER:-test-user}"

# 查找 MCP 配置文件（支持 mcp_config.json 和 config.json 两种格式）
# 用法: _find_config_file <server_dir>
# 返回: 配置文件路径（或空字符串）
_find_config_file() {
    local server_dir="$1"
    if [[ -f "${server_dir}/mcp_config.json" ]]; then
        echo "${server_dir}/mcp_config.json"
    elif [[ -f "${server_dir}/config.json" ]]; then
        echo "${server_dir}/config.json"
    fi
}

# 在所有扫描路径中查找 server 目录
# 用法: _find_server_dir <server_name>
# 返回: server 目录的绝对路径（或空字符串）
_find_server_dir() {
    local server_name="$1"
    local scan_path
    for scan_path in "${MCP_SERVERS_PATH}" "${MCP_CENTER_PATH}"; do
        local candidate="${scan_path}/${server_name}"
        if [[ -d "$candidate" ]]; then
            local config
            config=$(_find_config_file "$candidate")
            if [[ -n "$config" ]]; then
                echo "$candidate"
                return
            fi
        fi
    done
}

# 获取所有扫描路径列表（过滤不存在的路径）
_scan_paths() {
    local scan_path
    for scan_path in "${MCP_SERVERS_PATH}" "${MCP_CENTER_PATH}"; do
        if [[ -d "${scan_path}" ]]; then
            echo "${scan_path}"
        fi
    done
}

# 通过 daemon UDS socket 发请求
_daemon_curl() {
    local method="$1"
    local path="$2"
    shift 2
    curl -s --max-time 30 --unix-socket "${SOCK_PATH}" \
        -X "${method}" \
        -H "X-Witty-User: ${WITTY_USER}" \
        -H "Content-Type: application/json" \
        "$@" \
        "http://localhost${path}"
}

# 检查 daemon 是否可用
_daemon_available() {
    [[ -S "${SOCK_PATH}" ]] && \
        _daemon_curl GET /health >/dev/null 2>&1
}

# 检查 mcp-cli 是否可用
_mcpcli_available() {
    command -v mcp-cli >/dev/null 2>&1 || \
    [[ -x "${HOME}/.local/bin/mcp-cli" ]]
}

# 获取 mcp-cli 路径
_mcpcli_cmd() {
    if command -v mcp-cli >/dev/null 2>&1; then
        echo "mcp-cli"
    elif [[ -x "${HOME}/.local/bin/mcp-cli" ]]; then
        echo "${HOME}/.local/bin/mcp-cli"
    fi
}

# 子命令: 列出 MCP 服务器（优先通过 daemon，回退到目录扫描）
_test_mcps_list() {
    if _daemon_available; then
        log_info "通过 daemon (UDS) 查询 MCP 服务器..."
        echo ""
        
        local response
        response=$(_daemon_curl GET "/v1/servers?include_disabled=true")
        
        local success
        success=$(echo "$response" | python3 -c "import json,sys; print(json.load(sys.stdin).get('success', False))" 2>/dev/null)
        
        if [[ "$success" != "True" ]]; then
            log_error "daemon 查询失败:"
            echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
            return 1
        fi
        
        # 格式化输出
        echo "$response" | python3 -c "
import json, sys
d = json.load(sys.stdin)
servers = d['data']
ready = degraded = unavail = 0
for s in servers:
    mid = s['mcp_id']
    status = s['status']
    source = s['source']
    name = s.get('name', mid)
    reason = s.get('status_reason') or ''
    
    if status == 'ready':
        icon = '\033[0;32m✓\033[0m'
        ready += 1
    elif status == 'degraded':
        icon = '\033[1;33m⚠\033[0m'
        degraded += 1
    else:
        icon = '\033[0;31m✗\033[0m'
        unavail += 1
    
    display = f'{mid} ({name})' if name != mid else mid
    line = f'  {icon} {display:45s} [{source:6s}] {status:12s}'
    if reason:
        line += f' - {reason[:50]}'
    print(line)

print()
total = ready + degraded + unavail
print(f'  共 {total} 个服务器: \033[0;32m{ready} ready\033[0m, \033[1;33m{degraded} degraded\033[0m, \033[0;31m{unavail} unavailable\033[0m')
" 2>/dev/null
        
    else
        log_warn "daemon 未运行, 扫描本地目录..."
        echo ""
        
        local found_any_path=false
        local count=0
        
        local scan_path
        while IFS= read -r scan_path; do
            found_any_path=true
            log_info "扫描路径: ${scan_path}"
            
            while IFS= read -r -d '' dir; do
                local server_name=$(basename "$dir")
                
                if [[ -f "$dir/mcp_config.json" ]] || [[ -f "$dir/config.json" ]]; then
                    ((++count))
                    log_success "✓ $server_name (有 MCP 配置)"
                elif [[ -f "$dir/pyproject.toml" ]]; then
                    ((++count))
                    log_success "✓ $server_name (Python 项目)"
                elif [[ -f "$dir/package.json" ]]; then
                    ((++count))
                    log_success "✓ $server_name (Node.js 项目)"
                fi
            done < <(find "${scan_path}" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null || true)
        done < <(_scan_paths)
        
        if [[ "$found_any_path" != "true" ]]; then
            log_error "MCP 服务器路径不存在:"
            log_error "  RPM: ${MCP_SERVERS_PATH}"
            log_error "  mcp_center: ${MCP_CENTER_PATH}"
            log_info "请先安装 MCP Server RPM 包或部署 mcp_center"
            return 1
        fi
        
        echo ""
        if [[ $count -eq 0 ]]; then
            log_warn "未找到 MCP 服务器"
        else
            log_success "共发现 ${count} 个 MCP 服务器"
        fi
    fi
}

# 子命令: 用 mcp-cli ping 测试服务器
_test_mcps_ping() {
    local server_name="$1"
    
    if ! _mcpcli_available; then
        log_error "mcp-cli 未安装"
        log_info "请运行: uv tool install mcp-cli"
        log_info "安装后如不在 PATH 中，请运行: uv tool update-shell 或 source ~/.bashrc"
        return 1
    fi
    
    local server_dir
    server_dir=$(_find_server_dir "${server_name}")
    if [[ -z "$server_dir" ]]; then
        log_error "未找到服务器 ${server_name}（已扫描: ${MCP_SERVERS_PATH}, ${MCP_CENTER_PATH}）"
        return 1
    fi
    
    local config_file
    config_file=$(_find_config_file "${server_dir}")
    
    # 从配置文件解析出 server key
    local server_key
    server_key=$(python3 -c "
import json
with open('${config_file}') as f:
    d = json.load(f)
keys = list(d.get('mcpServers', {}).keys())
print(keys[0] if keys else '')
" 2>/dev/null)
    
    if [[ -z "$server_key" ]]; then
        log_error "无法解析 mcpServers key: ${config_file}"
        return 1
    fi
    
    local mcpcli=$(_mcpcli_cmd)
    log_info "用 mcp-cli ping 测试: ${server_name} (key=${server_key})"
    timeout 30 ${mcpcli} ping \
        --config-file "${config_file}" \
        --server "${server_key}" \
        -q 2>&1 || log_error "ping 失败"
}

# 子命令: 用 mcp-cli 列出工具 (JSON 输出)
_test_mcps_tools() {
    local server_name="$1"
    
    # 优先用 daemon
    if _daemon_available; then
        log_info "通过 daemon 查询 ${server_name} 的工具列表..."
        local response
        response=$(_daemon_curl GET "/v1/servers/${server_name}/tools")
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
        return
    fi
    
    # 回退到 mcp-cli
    if ! _mcpcli_available; then
        log_error "daemon 未运行且 mcp-cli 未安装"
        log_info "请运行: uv tool install mcp-cli"
        log_info "安装后如不在 PATH 中，请运行: uv tool update-shell 或 source ~/.bashrc"
        return 1
    fi
    
    local server_dir
    server_dir=$(_find_server_dir "${server_name}")
    if [[ -z "$server_dir" ]]; then
        log_error "未找到服务器 ${server_name}（已扫描: ${MCP_SERVERS_PATH}, ${MCP_CENTER_PATH}）"
        return 1
    fi
    
    local config_file
    config_file=$(_find_config_file "${server_dir}")
    
    local server_key
    server_key=$(python3 -c "
import json
with open('${config_file}') as f:
    d = json.load(f)
keys = list(d.get('mcpServers', {}).keys())
print(keys[0] if keys else '')
" 2>/dev/null)
    
    local mcpcli=$(_mcpcli_cmd)
    log_info "用 mcp-cli 查询: ${server_name} (key=${server_key})"
    # mcp-cli 会在 stdout 混入日志行，用 sed 过滤只保留 JSON 部分
    timeout 60 ${mcpcli} tools \
        --config-file "${config_file}" \
        --server "${server_key}" \
        --raw -q --log-level ERROR 2>&1 | sed -n '/^\[/,$p'
}

# 子命令: 通过 daemon 调用工具
_test_mcps_call() {
    local server_name="$1"
    local tool_name="$2"
    local tool_args="${3:-{\}}"
    
    if ! _daemon_available; then
        log_error "daemon 未运行, 无法调用工具"
        log_info "请先启动服务: ./scripts/test_env.sh start"
        return 1
    fi
    
    log_info "调用 ${server_name}/${tool_name}..."
    local response
    response=$(_daemon_curl POST "/v1/me/servers/${server_name}/tools/${tool_name}:call" \
        -d "{\"arguments\": ${tool_args}}")
    
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
}

# 子命令: 用 mcp-cli ping 所有服务器
_test_mcps_ping_all() {
    if ! _mcpcli_available; then
        log_error "mcp-cli 未安装"
        log_info "请运行: uv tool install mcp-cli"
        log_info "安装后如不在 PATH 中，请运行: uv tool update-shell 或 source ~/.bashrc"
        return 1
    fi
    
    local mcpcli=$(_mcpcli_cmd)
    local total=0
    local passed=0
    local failed=0
    
    log_info "用 mcp-cli 逐个 ping 测试..."
    echo ""
    
    local scan_path
    while IFS= read -r scan_path; do
        log_info "扫描: ${scan_path}"
        
        while IFS= read -r -d '' dir; do
            local server_name=$(basename "$dir")
            local config_file
            config_file=$(_find_config_file "${dir}")
            
            if [[ -z "$config_file" ]]; then
                continue
            fi
            
            local server_key
            server_key=$(python3 -c "
import json
with open('${config_file}') as f:
    d = json.load(f)
keys = list(d.get('mcpServers', {}).keys())
print(keys[0] if keys else '')
" 2>/dev/null)
            
            if [[ -z "$server_key" ]]; then
                continue
            fi
            
            ((++total))
            printf "  %-30s " "${server_name}"
            
            if timeout 30 ${mcpcli} ping \
                --config-file "${config_file}" \
                --server "${server_key}" \
                -q >/dev/null 2>&1; then
                echo -e "${GREEN}✓ OK${NC}"
                ((++passed))
            else
                echo -e "${RED}✗ FAIL${NC}"
                ((++failed))
            fi
        done < <(find "${scan_path}" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null || true)
    done < <(_scan_paths)
    
    echo ""
    log_info "结果: ${total} 个测试, ${GREEN}${passed} 通过${NC}, ${RED}${failed} 失败${NC}"
    
    [[ $failed -eq 0 ]]
}

# test-mcps 主入口
test_mcps() {
    check_linux
    
    local subcmd="${1:-list}"
    shift 2>/dev/null || true
    
    case "${subcmd}" in
        list|"")
            _test_mcps_list
            ;;
        ping-all)
            _test_mcps_ping_all
            ;;
        ping)
            if [[ -z "${1:-}" ]]; then
                log_error "缺少参数: test-mcps ping <server_name>"
                return 1
            fi
            _test_mcps_ping "$1"
            ;;
        tools)
            if [[ -z "${1:-}" ]]; then
                log_error "缺少参数: test-mcps tools <server_name>"
                return 1
            fi
            _test_mcps_tools "$1"
            ;;
        call)
            if [[ -z "${1:-}" ]] || [[ -z "${2:-}" ]]; then
                log_error "缺少参数: test-mcps call <server_name> <tool_name> [args_json]"
                return 1
            fi
            _test_mcps_call "$1" "$2" "${3:-{\}}"
            ;;
        help)
            cat <<HELP
MCP 测试子命令:

  test-mcps [list]                                列出所有 MCP 服务器
  test-mcps ping-all                              用 mcp-cli 逐个 ping 所有服务器
  test-mcps ping <server>                         用 mcp-cli ping 单个服务器
  test-mcps tools <server>                        列出服务器的 tools (JSON)
  test-mcps call <server> <tool> [args_json]      通过 daemon 调用工具
  test-mcps help                                  显示此帮助

查询方式:
  - list/tools/call: 优先通过 daemon UDS socket 查询
  - ping/ping-all: 使用 mcp-cli 直连 MCP 服务器
  - 如果 daemon 未运行, list 回退到目录扫描, tools 回退到 mcp-cli

环境变量:
  WITTY_USER          daemon 查询的用户 (默认: test-user)
  MCP_SERVERS_PATH    RPM MCP 服务器目录 (默认: /opt/mcp-servers/servers)
  MCP_CENTER_PATH     mcp_center MCP 目录 (默认: /usr/lib/sysagent/mcp_center/mcp_config)

示例:
  ./scripts/test_env.sh test-mcps                          # 列出所有
  ./scripts/test_env.sh test-mcps ping-all                 # ping 所有
  ./scripts/test_env.sh test-mcps ping git_mcp             # ping 单个
  ./scripts/test_env.sh test-mcps tools cvekit_mcp         # 查看工具
  ./scripts/test_env.sh test-mcps call git_mcp git_status '{"repo_path":"/tmp/repo"}'
HELP
            ;;
        *)
            log_error "未知子命令: ${subcmd}"
            log_info "运行 './scripts/test_env.sh test-mcps help' 查看帮助"
            return 1
            ;;
    esac
}

# ============================================
# 健康检查
# ============================================

health_check() {
    log_info "执行健康检查..."
    
    check_linux
    
    local errors=0
    
    # 检查服务状态
    log_info "检查服务状态..."
    if run_as_root systemctl is-active ${SERVICE_NAME} >/dev/null 2>&1; then
        log_success "✓ 服务运行中"
    else
        log_error "✗ 服务未运行"
        ((++errors))
    fi
    
    # 检查套接字
    log_info "检查 UDS 套接字..."
    if [[ -S "${RUNTIME_DIR}/mcp-manager.sock" ]]; then
        log_success "✓ UDS 套接字存在"
    else
        log_error "✗ UDS 套接字不存在"
        ((++errors))
    fi
    
    # 检查目录权限
    log_info "检查目录权限..."
    if [[ -d "${STATE_DIR}" ]] && [[ -w "${STATE_DIR}" ]]; then
        log_success "✓ 状态目录权限正常"
    else
        log_error "✗ 状态目录权限异常"
        ((++errors))
    fi
    
    # 检查 MCP 服务器路径
    log_info "检查 MCP 服务器路径..."
    if [[ -d "${MCP_SERVERS_PATH}" ]]; then
        local count=$(ls -1d ${MCP_SERVERS_PATH}/*/ 2>/dev/null | wc -l)
        log_success "✓ RPM MCP 路径存在: ${MCP_SERVERS_PATH} (${count} 个子目录)"
    else
        log_warn "⚠ RPM MCP 路径不存在: ${MCP_SERVERS_PATH}"
        log_info "  如需测试 RPM MCP，请安装 MCP Server RPM 包"
    fi
    if [[ -d "${MCP_CENTER_PATH}" ]]; then
        local count=$(ls -1d ${MCP_CENTER_PATH}/*/ 2>/dev/null | wc -l)
        log_success "✓ mcp_center 路径存在: ${MCP_CENTER_PATH} (${count} 个子目录)"
    else
        log_warn "⚠ mcp_center 路径不存在: ${MCP_CENTER_PATH}"
        log_info "  如需测试 mcp_center MCP，请部署 mcp_center"
    fi
    
    # 检查 witty-mcp 用户
    log_info "检查 witty-mcp 用户..."
    if id witty-mcp >/dev/null 2>&1; then
        log_success "✓ witty-mcp 用户存在"
    else
        log_error "✗ witty-mcp 用户不存在"
        ((++errors))
    fi
    
    echo ""
    if [[ ${errors} -eq 0 ]]; then
        log_success "============================================"
        log_success "健康检查通过 ✓"
        log_success "============================================"
        return 0
    else
        log_error "============================================"
        log_error "健康检查失败 (${errors} 个错误)"
        log_error "============================================"
        return 1
    fi
}

# ============================================
# 帮助信息
# ============================================

show_help() {
    cat <<EOF
Witty MCP Manager 测试环境管理脚本

适用环境: openEuler 24.03 LTS SP3 (或其他 Linux)
运行位置: 在 Linux 本地直接执行

前提条件:
    ✓ openEuler 24.03 LTS SP3 (或其他 Linux) 已配置
    ✓ 具有 root 权限或 sudo 权限
    ✓ 本仓库已克隆到本地
    ✓ MCP 服务器已安装 (可选，test-mcps 命令需要)
      - RPM MCP: 通过 dnf 安装到 /opt/mcp-servers/servers
      - mcp_center MCP: 部署到 /usr/lib/sysagent/mcp_center/mcp_config

使用方法:
    cd /path/to/euler-copilot/framework/witty_mcp_manager
    $0 COMMAND [OPTIONS]

命令:
    setup-dev          配置本地开发环境 (uv sync)
    install            安装服务到系统
    start              启动守护进程
    stop               停止守护进程
    restart            重启守护进程
    status             检查守护进程状态
    logs [LINES]       查看守护进程日志 (默认 100 行)
    logs-f [LINES]     跟随查看日志
    clean              清理配置和状态目录
    clean-all          完全清理 (包括卸载服务)
    test-mcps [subcmd]  测试 MCP 服务器 (运行 test-mcps help 查看子命令)
    health             健康检查
    help               显示此帮助信息

环境变量:
    MCP_SERVERS_PATH   RPM MCP 服务器安装路径 (默认: /opt/mcp-servers/servers)
    MCP_CENTER_PATH    mcp_center MCP 配置路径 (默认: /usr/lib/sysagent/mcp_center/mcp_config)
    STATE_DIR          状态目录 (默认: /var/lib/witty-mcp-manager)
    RUNTIME_DIR        运行时目录 (默认: /run/witty)
    CONFIG_DIR         配置目录 (默认: /etc/witty)
    WITTY_USER         daemon 查询用户 (默认: test-user)

示例:
    # 首次设置
    $0 setup-dev                    # 配置本地开发环境
    $0 install                      # 安装服务
    $0 start                        # 启动服务
    
    # 日常操作
    $0 status                       # 查看状态
    $0 logs 50                      # 查看最近 50 行日志
    $0 logs-f                       # 跟随查看日志
    $0 restart                      # 重启服务
    
    # MCP 测试
    $0 test-mcps                    # 列出所有 MCP 服务器
    $0 test-mcps ping-all           # ping 所有服务器 (mcp-cli)
    $0 test-mcps ping git_mcp       # ping 单个服务器
    $0 test-mcps tools cvekit_mcp   # 查看工具列表 (JSON)
    $0 test-mcps call git_mcp git_status '{"repo_path":"/tmp"}'  # 调用工具
    $0 health                       # 健康检查
    
    # 清理
    $0 clean                        # 清理状态文件
    $0 clean-all                    # 完全清理
    
    # 使用自定义路径
    MCP_SERVERS_PATH=/custom/path $0 test-mcps

注意:
    - 本脚本必须在 Linux 系统上运行
    - 大部分命令需要 root 权限（可使用 root 用户或 sudo）
    - 使用 clean 或 clean-all 前会提示确认
    - MCP 服务器可选安装，脚本会自动扫描可用的路径
      - 支持两个扫描路径: MCP_SERVERS_PATH (RPM) 和 MCP_CENTER_PATH (mcp_center)
      - 兼容部分安装的情况（只有 RPM 或只有 mcp_center）
    - test-mcps 优先通过 daemon UDS socket 查询，回退到目录扫描
    - mcp-cli ping 需要 uv tool install mcp-cli (安装后如不在 PATH 中，请运行 uv tool update-shell)

相关文档:
    - 详细使用指南: scripts/reference/test_env/TEST_ENV_GUIDE.md
    - 使用示例: scripts/reference/test_env/EXAMPLES.md
    - 快速参考: scripts/reference/test_env/QUICK_REFERENCE.sh

EOF
}

# ============================================
# 主程序
# ============================================

main() {
    if [[ $# -eq 0 ]]; then
        show_help
        exit 0
    fi
    
    local command="$1"
    shift
    
    case "${command}" in
        setup-dev)
            setup_dev
            ;;
        install)
            install_service
            ;;
        start)
            start_service
            ;;
        stop)
            stop_service
            ;;
        restart)
            restart_service
            ;;
        status)
            check_status
            ;;
        logs)
            show_logs "${1:-100}"
            ;;
        logs-f)
            show_logs "${1:-100}" "follow"
            ;;
        clean)
            clean_state
            ;;
        clean-all)
            clean_all
            ;;
        test-mcps)
            test_mcps "$@"
            ;;
        health)
            health_check
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: ${command}"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
