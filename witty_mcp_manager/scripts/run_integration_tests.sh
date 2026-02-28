#!/bin/bash
# Witty MCP Manager 集成测试启动脚本
#
# 此脚本用于在 openEuler 24.03 LTS SP3 虚拟机上运行 Witty MCP Manager 的集成测试。
#
# 环境要求:
# - openEuler 24.03 LTS SP3 或兼容系统
# - Python 3.11+
# - uv 包管理器
# - witty-mcp-manager daemon 运行中
#
# 使用方法:
#   # 直接运行（自动设置环境变量）
#   ./scripts/run_integration_tests.sh
#
#   # 指定测试类
#   ./scripts/run_integration_tests.sh TestIPCHealth
#
#   # 指定测试方法
#   ./scripts/run_integration_tests.sh TestIPCHealth::test_health_endpoint
#
#   # 使用详细输出
#   VERBOSE=1 ./scripts/run_integration_tests.sh
#
#   # 生成 HTML 报告（需要 pytest-html）
#   REPORT=1 ./scripts/run_integration_tests.sh

set -e

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查前置条件
check_prerequisites() {
    log_info "检查前置条件..."

    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 未安装"
        exit 1
    fi
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    log_info "Python 版本: $PYTHON_VERSION"

    # 检查 uv
    if ! command -v uv &> /dev/null; then
        log_error "uv 包管理器未安装"
        log_info "安装方法: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    UV_VERSION=$(uv --version 2>&1 | head -n1)
    log_info "uv 版本: $UV_VERSION"

    # 检查 witty-mcp CLI
    if ! command -v witty-mcp &> /dev/null; then
        log_warn "witty-mcp CLI 未在 PATH 中找到"
        log_info "将尝试使用 'uv run witty-mcp' 代替"
    else
        WITTY_VERSION=$(witty-mcp version 2>&1 || echo "unknown")
        log_info "witty-mcp 版本: $WITTY_VERSION"
    fi

    # 检查 daemon socket
    SOCKET_PATH="/run/witty/mcp-manager.sock"
    if [ -S "$SOCKET_PATH" ]; then
        log_success "Daemon socket 存在: $SOCKET_PATH"
    else
        log_error "Daemon socket 不存在: $SOCKET_PATH"
        log_info "请先启动 daemon: systemctl start witty-mcp-manager"
        exit 1
    fi

    # 检查 MCP 服务器目录
    MCP_DIR="/opt/mcp-servers"
    if [ -d "$MCP_DIR" ]; then
        MCP_COUNT=$(ls -d "$MCP_DIR"/servers/*/ 2>/dev/null | wc -l)
        log_info "发现 MCP 服务器目录: $MCP_DIR ($MCP_COUNT 个服务器)"
    else
        log_warn "MCP 服务器目录不存在: $MCP_DIR"
    fi

    # 检查用户 override 目录权限
    OVERRIDE_USERS_DIR="/var/lib/witty-mcp-manager/overrides/users"
    if [ -d "$OVERRIDE_USERS_DIR" ]; then
        PERMS=$(stat -c '%a' "$OVERRIDE_USERS_DIR" 2>/dev/null || stat -f '%Lp' "$OVERRIDE_USERS_DIR" 2>/dev/null)
        if [ "$PERMS" = "1777" ] || [ -w "$OVERRIDE_USERS_DIR" ]; then
            log_success "用户 override 目录权限正确: $OVERRIDE_USERS_DIR"
        else
            log_warn "用户 override 目录可能无写入权限: $OVERRIDE_USERS_DIR (权限: $PERMS)"
            log_info "如果 enable/disable 测试失败，请运行: sudo chmod 1777 $OVERRIDE_USERS_DIR"
        fi

        # 清理旧的测试用户目录（test_user_* 格式）
        OLD_TEST_DIRS=$(find "$OVERRIDE_USERS_DIR" -maxdepth 1 -type d -name 'test_user_*' 2>/dev/null | wc -l)
        if [ "$OLD_TEST_DIRS" -gt 0 ]; then
            log_info "发现 $OLD_TEST_DIRS 个旧测试用户目录，正在清理..."
            find "$OVERRIDE_USERS_DIR" -maxdepth 1 -type d -name 'test_user_*' -exec rm -rf {} + 2>/dev/null || true
            log_success "旧测试用户目录已清理"
        fi
    else
        log_warn "用户 override 目录不存在: $OVERRIDE_USERS_DIR"
    fi

    log_success "前置条件检查完成"
}

# 安装测试依赖
install_dependencies() {
    log_info "安装测试依赖..."
    cd "$PROJECT_ROOT"

    # 同步依赖
    uv sync --extra dev

    log_success "依赖安装完成"
}

# 运行测试
run_tests() {
    log_info "运行集成测试..."
    cd "$PROJECT_ROOT"

    # 设置环境变量
    export WITTY_TEST_VM=1

    # 构建 pytest 参数
    PYTEST_ARGS=()

    # 添加详细输出
    if [ "${VERBOSE:-0}" = "1" ]; then
        PYTEST_ARGS+=("-v" "-s")
    else
        PYTEST_ARGS+=("-v")
    fi

    # 添加测试报告
    if [ "${REPORT:-0}" = "1" ]; then
        REPORT_FILE="test_report_$(date +%Y%m%d_%H%M%S).html"
        PYTEST_ARGS+=("--html=$REPORT_FILE" "--self-contained-html")
        log_info "测试报告将生成到: $REPORT_FILE"
    fi

    # 添加测试文件路径
    TEST_FILE="tests/integration/test_witty_mcp_manager.py"

    # 添加用户指定的测试
    if [ -n "$1" ]; then
        TEST_FILE="$TEST_FILE::$1"
    fi

    PYTEST_ARGS+=("$TEST_FILE")

    # 运行测试
    log_info "执行: uv run pytest ${PYTEST_ARGS[*]}"
    uv run pytest "${PYTEST_ARGS[@]}"

    log_success "测试执行完成"
}

# 显示帮助信息
show_help() {
    cat << EOF
Witty MCP Manager 集成测试脚本

使用方法:
    $0 [选项] [测试类或方法]

选项:
    -h, --help      显示此帮助信息
    -c, --check     仅检查前置条件，不运行测试
    -i, --install   仅安装依赖，不运行测试

环境变量:
    VERBOSE=1       启用详细输出
    REPORT=1        生成 HTML 测试报告

示例:
    $0                                    # 运行所有测试
    $0 TestIPCHealth                      # 运行指定测试类
    $0 TestIPCHealth::test_health_endpoint # 运行指定测试方法
    VERBOSE=1 $0                          # 详细输出
    REPORT=1 $0                           # 生成报告

支持的测试类:
    TestIPCHealth           健康检查接口测试
    TestIPCRegistry         Registry 接口测试
    TestIPCEnableDisable    启用/禁用接口测试
    TestIPCTools            Tools 接口测试
    TestIPCToolCall         Tool Call 接口测试
    TestIPCRuntime          Runtime 接口测试
    TestCLIVersion          CLI 版本命令测试
    TestCLIServers          CLI servers 子命令测试
    TestCLIEnableDisable    CLI enable/disable 命令测试
    TestCLIRuntime          CLI runtime 子命令测试
    TestCLIConfig           CLI config 子命令测试
    TestEndToEnd            端到端集成测试
    TestConcurrency         并发测试
    TestErrorHandling       错误处理测试
    TestDataCollection      数据收集测试

EOF
}

# 主函数
main() {
    case "${1:-}" in
        -h|--help)
            show_help
            exit 0
            ;;
        -c|--check)
            check_prerequisites
            exit 0
            ;;
        -i|--install)
            check_prerequisites
            install_dependencies
            exit 0
            ;;
        *)
            check_prerequisites
            install_dependencies
            run_tests "$1"
            ;;
    esac
}

main "$@"
