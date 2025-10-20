#!/bin/bash

set -eo pipefail

# 颜色定义
RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
NC='\033[0m'

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOMATION_SCRIPT="$SCRIPT_DIR/authelia_automation.sh"

# 默认配置
DEFAULT_USERNAME="openEuler"
DEFAULT_PASSWORD="openEuler12#\$"
DEFAULT_EMAIL="openEuler@example.com"
DEFAULT_CLIENT_ID="euler-copilot"
DEFAULT_CLIENT_NAME="Euler Copilot"

# 打印帮助信息
print_help() {
    echo -e "${GREEN}Authelia 快速配置脚本${NC}"
    echo -e "${GREEN}用法: $0 [选项]${NC}"
    echo ""
    echo -e "${BLUE}选项:${NC}"
    echo -e "  --help                          显示帮助信息"
    echo -e "  --interactive                   交互式配置"
    echo -e "  --default                       使用默认配置快速设置"
    echo -e "  --username <用户名>             指定用户名 (默认: $DEFAULT_USERNAME)"
    echo -e "  --password <密码>               指定密码 (默认: $DEFAULT_PASSWORD)"
    echo -e "  --email <邮箱>                  指定邮箱 (默认: $DEFAULT_EMAIL)"
    echo -e "  --client-id <客户端ID>          指定OIDC客户端ID (默认: $DEFAULT_CLIENT_ID)"
    echo -e "  --client-name <客户端名称>      指定OIDC客户端名称 (默认: $DEFAULT_CLIENT_NAME)"
    echo -e "  --redirect-uri <重定向URI>      指定OIDC重定向URI"
    echo ""
    echo -e "${BLUE}示例:${NC}"
    echo -e "  # 使用默认配置快速设置"
    echo -e "  $0 --default --redirect-uri 'http://127.0.0.1:30080/auth/callback'"
    echo ""
    echo -e "  # 交互式配置"
    echo -e "  $0 --interactive"
    echo ""
    echo -e "  # 自定义配置"
    echo -e "  $0 --username myuser --password 'mypass123' --email myuser@example.com \\"
    echo -e "     --client-id my-client --redirect-uri 'http://localhost:3000/callback'"
    echo ""
}

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    # 检查kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl 未安装或不在PATH中"
        return 1
    fi
    
    # 检查自动化脚本
    if [ ! -f "$AUTOMATION_SCRIPT" ]; then
        log_error "自动化脚本不存在: $AUTOMATION_SCRIPT"
        return 1
    fi
    
    # 检查脚本权限
    if [ ! -x "$AUTOMATION_SCRIPT" ]; then
        log_info "设置自动化脚本执行权限"
        chmod +x "$AUTOMATION_SCRIPT"
    fi
    
    # 检查Authelia服务状态
    if ! kubectl get deployment authelia -n euler-copilot &> /dev/null; then
        log_error "Authelia服务未部署，请先运行安装脚本"
        return 1
    fi
    
    log_success "依赖检查通过"
}

# 获取用户输入
get_user_input() {
    echo -e "${BLUE}=== Authelia 交互式配置 ===${NC}"
    echo ""
    
    # 用户配置
    echo -e "${YELLOW}用户配置:${NC}"
    read -p "用户名 [$DEFAULT_USERNAME]: " USERNAME
    USERNAME=${USERNAME:-$DEFAULT_USERNAME}
    
    read -s -p "密码 [默认密码]: " PASSWORD
    echo
    PASSWORD=${PASSWORD:-$DEFAULT_PASSWORD}
    
    read -p "邮箱 [$DEFAULT_EMAIL]: " EMAIL
    EMAIL=${EMAIL:-$DEFAULT_EMAIL}
    
    # 固定用户组为admins
    GROUPS="admins"
    
    echo ""
    
    # OIDC配置
    echo -e "${YELLOW}OIDC客户端配置:${NC}"
    read -p "客户端ID [$DEFAULT_CLIENT_ID]: " CLIENT_ID
    CLIENT_ID=${CLIENT_ID:-$DEFAULT_CLIENT_ID}
    
    read -p "客户端名称 [$DEFAULT_CLIENT_NAME]: " CLIENT_NAME
    CLIENT_NAME=${CLIENT_NAME:-$DEFAULT_CLIENT_NAME}
    
    while [ -z "$REDIRECT_URI" ]; do
        read -p "重定向URI (必填): " REDIRECT_URI
        if [ -z "$REDIRECT_URI" ]; then
            log_error "重定向URI不能为空"
        fi
    done
    
    echo ""
    
    # 确认配置
    echo -e "${BLUE}=== 配置确认 ===${NC}"
    echo -e "${YELLOW}用户信息:${NC}"
    echo "  用户名: $USERNAME"
    echo "  邮箱: $EMAIL"
    echo ""
    echo -e "${YELLOW}OIDC客户端:${NC}"
    echo "  客户端ID: $CLIENT_ID"
    echo "  客户端名称: $CLIENT_NAME"
    echo "  重定向URI: $REDIRECT_URI"
    echo ""
    
    read -p "确认以上配置？(y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_info "配置已取消"
        exit 0
    fi
}

# 执行配置
execute_setup() {
    log_info "开始执行Authelia配置..."
    
    # 1. 生成OIDC密钥
    log_info "步骤 1/4: 生成OIDC密钥"
    if ! "$AUTOMATION_SCRIPT" generate-keys; then
        log_error "OIDC密钥生成失败"
        return 1
    fi
    
    # 2. 创建用户
    log_info "步骤 2/4: 创建用户 $USERNAME"
    if ! "$AUTOMATION_SCRIPT" create-user "$USERNAME" "$PASSWORD" "$EMAIL" "$GROUPS"; then
        log_warning "用户创建失败，可能用户已存在"
    fi
    
    # 3. 创建OIDC客户端
    log_info "步骤 3/4: 创建OIDC客户端 $CLIENT_ID"
    if ! "$AUTOMATION_SCRIPT" create-oidc-client "$CLIENT_ID" "$CLIENT_NAME" "$REDIRECT_URI"; then
        log_error "OIDC客户端创建失败"
        return 1
    fi
    
    # 4. 重启服务
    log_info "步骤 4/4: 重启Authelia服务"
    if ! "$AUTOMATION_SCRIPT" restart-service; then
        log_error "服务重启失败"
        return 1
    fi
    
    log_success "Authelia配置完成！"
}

# 显示配置结果
show_results() {
    echo ""
    echo -e "${GREEN}=== 配置完成 ===${NC}"
    echo ""
    echo -e "${YELLOW}登录信息:${NC}"
    echo "  用户名: $USERNAME"
    echo "  密码: $PASSWORD"
    echo "  邮箱: $EMAIL"
    echo ""
    echo -e "${YELLOW}OIDC客户端信息:${NC}"
    echo "  客户端ID: $CLIENT_ID"
    echo "  客户端名称: $CLIENT_NAME"
    echo "  重定向URI: $REDIRECT_URI"
    
    # 显示客户端密钥（如果存在）
    if [ -f "/tmp/authelia_oidc_clients" ]; then
        echo ""
        echo -e "${YELLOW}客户端密钥信息:${NC}"
        tail -n 10 /tmp/authelia_oidc_clients | grep -E "(Client ID|Client Secret)" | tail -n 2
    fi
    
    echo ""
    echo -e "${BLUE}后续步骤:${NC}"
    echo "1. 验证Authelia服务状态: kubectl get pods -n euler-copilot"
    echo "2. 检查服务日志: kubectl logs -n euler-copilot deployment/authelia"
    echo "3. 测试OIDC配置: curl -s http://<authelia-address>/.well-known/openid_configuration"
    echo ""
    echo -e "${YELLOW}管理命令:${NC}"
    echo "- 列出用户: $AUTOMATION_SCRIPT list-users"
    echo "- 列出OIDC客户端: $AUTOMATION_SCRIPT list-oidc-clients"
    echo "- 备份配置: $AUTOMATION_SCRIPT backup-config"
    echo ""
}

# 默认配置设置
setup_default_config() {
    if [ -z "$REDIRECT_URI" ]; then
        log_error "使用默认配置时必须指定 --redirect-uri"
        return 1
    fi
    
    USERNAME="$DEFAULT_USERNAME"
    PASSWORD="$DEFAULT_PASSWORD"
    EMAIL="$DEFAULT_EMAIL"
    GROUPS="admins"
    CLIENT_ID="$DEFAULT_CLIENT_ID"
    CLIENT_NAME="$DEFAULT_CLIENT_NAME"
    
    log_info "使用默认配置:"
    log_info "  用户名: $USERNAME"
    log_info "  邮箱: $EMAIL"
    log_info "  客户端ID: $CLIENT_ID"
    log_info "  重定向URI: $REDIRECT_URI"
}

# 解析命令行参数
parse_args() {
    local interactive=false
    local use_default=false
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help)
                print_help
                exit 0
                ;;
            --interactive)
                interactive=true
                shift
                ;;
            --default)
                use_default=true
                shift
                ;;
            --username)
                USERNAME="$2"
                shift 2
                ;;
            --password)
                PASSWORD="$2"
                shift 2
                ;;
            --email)
                EMAIL="$2"
                shift 2
                ;;
            --client-id)
                CLIENT_ID="$2"
                shift 2
                ;;
            --client-name)
                CLIENT_NAME="$2"
                shift 2
                ;;
            --redirect-uri)
                REDIRECT_URI="$2"
                shift 2
                ;;
            *)
                log_error "未知参数: $1"
                print_help
                exit 1
                ;;
        esac
    done
    
    # 处理配置模式
    if [ "$interactive" = true ]; then
        get_user_input
    elif [ "$use_default" = true ]; then
        setup_default_config
    else
        # 检查必需参数
        if [ -z "$REDIRECT_URI" ]; then
            log_error "必须指定重定向URI或使用交互模式"
            print_help
            exit 1
        fi
        
        # 使用提供的参数或默认值
        USERNAME="${USERNAME:-$DEFAULT_USERNAME}"
        PASSWORD="${PASSWORD:-$DEFAULT_PASSWORD}"
        EMAIL="${EMAIL:-$DEFAULT_EMAIL}"
        GROUPS="${GROUPS:-admins}"
        CLIENT_ID="${CLIENT_ID:-$DEFAULT_CLIENT_ID}"
        CLIENT_NAME="${CLIENT_NAME:-$DEFAULT_CLIENT_NAME}"
    fi
}

# 主函数
main() {
    echo -e "${GREEN}Authelia 快速配置脚本${NC}"
    echo -e "${BLUE}版本: 1.0.0${NC}"
    echo ""
    
    # 检查依赖
    check_dependencies || exit 1
    
    # 解析参数
    parse_args "$@"
    
    # 执行配置
    execute_setup || exit 1
    
    # 显示结果
    show_results
}

# 设置中断处理
trap 'echo -e "${RED}操作被中断！${NC}"; exit 1' INT

# 如果没有参数，显示帮助
if [ $# -eq 0 ]; then
    print_help
    exit 0
fi

# 执行主函数
main "$@"
