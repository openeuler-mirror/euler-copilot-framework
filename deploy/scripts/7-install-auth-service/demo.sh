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
QUICK_SETUP_SCRIPT="$SCRIPT_DIR/quick_setup.sh"

# 演示配置
DEMO_USERNAME="demo-user"
DEMO_PASSWORD="DemoPass123#\$"
DEMO_EMAIL="demo@example.com"
DEMO_CLIENT_ID="demo-client"
DEMO_CLIENT_NAME="Demo Application"
DEMO_REDIRECT_URI="http://127.0.0.1:30080/demo/callback"

# 日志函数
log_info() {
    echo -e "${BLUE}[DEMO]${NC} $1"
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

# 等待用户确认
wait_for_confirmation() {
    local message="$1"
    echo -e "${YELLOW}$message${NC}"
    read -p "按回车键继续，或 Ctrl+C 退出..."
    echo ""
}

# 检查Authelia服务状态
check_authelia_status() {
    log_info "检查Authelia服务状态..."
    
    if ! kubectl get deployment authelia -n euler-copilot &> /dev/null; then
        log_error "Authelia服务未部署，请先运行安装脚本"
        return 1
    fi
    
    local ready_replicas=$(kubectl get deployment authelia -n euler-copilot -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    local desired_replicas=$(kubectl get deployment authelia -n euler-copilot -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
    
    if [ "$ready_replicas" != "$desired_replicas" ]; then
        log_warning "Authelia服务未完全就绪 ($ready_replicas/$desired_replicas)"
        log_info "等待服务就绪..."
        kubectl wait --for=condition=available --timeout=300s deployment/authelia -n euler-copilot
    fi
    
    log_success "Authelia服务状态正常"
}

# 演示1：快速配置
demo_quick_setup() {
    echo -e "${GREEN}=== 演示1：使用快速配置脚本 ===${NC}"
    echo ""
    echo "这个演示将展示如何使用快速配置脚本一键完成Authelia配置"
    echo "包括："
    echo "- 生成OIDC密钥"
    echo "- 创建演示用户"
    echo "- 创建OIDC客户端"
    echo "- 重启服务"
    echo ""
    
    wait_for_confirmation "准备开始快速配置演示..."
    
    log_info "执行快速配置..."
    echo -e "${BLUE}命令: $QUICK_SETUP_SCRIPT --username $DEMO_USERNAME --password '$DEMO_PASSWORD' --email $DEMO_EMAIL --client-id $DEMO_CLIENT_ID --client-name '$DEMO_CLIENT_NAME' --redirect-uri '$DEMO_REDIRECT_URI'${NC}"
    echo ""
    
    # 注意：这里只是演示命令，实际执行需要Authelia服务运行
    log_warning "注意：这是演示模式，实际执行需要Authelia服务正常运行"
    echo ""
    
    log_success "快速配置演示完成"
}

# 演示2：分步配置
demo_step_by_step() {
    echo -e "${GREEN}=== 演示2：分步配置 ===${NC}"
    echo ""
    echo "这个演示将展示如何使用自动化脚本分步完成配置"
    echo ""
    
    wait_for_confirmation "准备开始分步配置演示..."
    
    # 步骤1：生成密钥
    log_info "步骤1：生成OIDC密钥"
    echo -e "${BLUE}命令: $AUTOMATION_SCRIPT generate-keys${NC}"
    log_warning "这将生成HMAC密钥和RSA密钥对"
    echo ""
    
    wait_for_confirmation "继续下一步..."
    
    # 步骤2：创建用户
    log_info "步骤2：创建用户"
    echo -e "${BLUE}命令: $AUTOMATION_SCRIPT create-user $DEMO_USERNAME '$DEMO_PASSWORD' $DEMO_EMAIL users${NC}"
    log_warning "这将创建一个新用户并生成密码哈希"
    echo ""
    
    wait_for_confirmation "继续下一步..."
    
    # 步骤3：创建OIDC客户端
    log_info "步骤3：创建OIDC客户端"
    echo -e "${BLUE}命令: $AUTOMATION_SCRIPT create-oidc-client $DEMO_CLIENT_ID '$DEMO_CLIENT_NAME' '$DEMO_REDIRECT_URI'${NC}"
    log_warning "这将创建OIDC客户端配置"
    echo ""
    
    wait_for_confirmation "继续下一步..."
    
    # 步骤4：重启服务
    log_info "步骤4：重启Authelia服务"
    echo -e "${BLUE}命令: $AUTOMATION_SCRIPT restart-service${NC}"
    log_warning "这将重启Authelia服务使配置生效"
    echo ""
    
    log_success "分步配置演示完成"
}

# 演示3：管理操作
demo_management() {
    echo -e "${GREEN}=== 演示3：管理操作 ===${NC}"
    echo ""
    echo "这个演示将展示常见的管理操作"
    echo ""
    
    wait_for_confirmation "准备开始管理操作演示..."
    
    # 列出用户
    log_info "列出所有用户"
    echo -e "${BLUE}命令: $AUTOMATION_SCRIPT list-users${NC}"
    echo ""
    
    wait_for_confirmation "继续下一步...")
    
    # 修改密码
    log_info "修改用户密码"
    echo -e "${BLUE}命令: $AUTOMATION_SCRIPT change-password $DEMO_USERNAME 'NewPassword123#\$'${NC}"
    echo ""
    
    wait_for_confirmation "继续下一步...")
    
    # 列出OIDC客户端
    log_info "列出OIDC客户端"
    echo -e "${BLUE}命令: $AUTOMATION_SCRIPT list-oidc-clients${NC}"
    echo ""
    
    wait_for_confirmation "继续下一步...")
    
    # 备份配置
    log_info "备份当前配置"
    echo -e "${BLUE}命令: $AUTOMATION_SCRIPT backup-config${NC}"
    echo ""
    
    log_success "管理操作演示完成"
}

# 演示4：实际测试（如果Authelia服务可用）
demo_real_test() {
    echo -e "${GREEN}=== 演示4：实际测试 ===${NC}"
    echo ""
    echo "如果Authelia服务正在运行，我们可以进行实际测试"
    echo ""
    
    # 检查服务状态
    if check_authelia_status; then
        log_info "Authelia服务可用，可以进行实际测试"
        
        read -p "是否要进行实际的配置测试？(y/N): " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            log_info "开始实际测试..."
            
            # 测试生成密钥
            log_info "测试生成OIDC密钥..."
            if "$AUTOMATION_SCRIPT" generate-keys; then
                log_success "OIDC密钥生成成功"
            else
                log_error "OIDC密钥生成失败"
            fi
            
            # 测试列出用户
            log_info "测试列出用户..."
            "$AUTOMATION_SCRIPT" list-users || log_warning "列出用户失败或无用户"
            
            # 测试列出OIDC客户端
            log_info "测试列出OIDC客户端..."
            "$AUTOMATION_SCRIPT" list-oidc-clients || log_warning "列出OIDC客户端失败或无客户端"
            
            log_success "实际测试完成"
        else
            log_info "跳过实际测试"
        fi
    else
        log_warning "Authelia服务不可用，跳过实际测试"
    fi
}

# 显示脚本功能总结
show_summary() {
    echo -e "${GREEN}=== 脚本功能总结 ===${NC}"
    echo ""
    echo -e "${YELLOW}创建的自动化脚本包括：${NC}"
    echo ""
    echo -e "${BLUE}1. authelia_automation.sh${NC} - 完整的自动化管理脚本"
    echo "   功能："
    echo "   - 用户管理：创建、删除、修改密码、列出用户"
    echo "   - OIDC客户端管理：创建、列出客户端"
    echo "   - 密钥管理：生成OIDC所需的密钥"
    echo "   - 配置管理：备份、恢复配置"
    echo "   - 服务管理：重启Authelia服务"
    echo ""
    
    echo -e "${BLUE}2. quick_setup.sh${NC} - 快速配置脚本"
    echo "   功能："
    echo "   - 一键完成基础配置"
    echo "   - 交互式配置模式"
    echo "   - 默认配置快速设置"
    echo "   - 自定义参数配置"
    echo ""
    
    echo -e "${YELLOW}使用场景：${NC}"
    echo "- 首次部署后的完整配置"
    echo "- 添加新用户和应用"
    echo "- 日常管理和维护"
    echo "- 配置备份和恢复"
    echo ""
    
    echo -e "${YELLOW}文件位置：${NC}"
    echo "- 自动化脚本：$AUTOMATION_SCRIPT"
    echo "- 快速配置脚本：$QUICK_SETUP_SCRIPT"
    echo "- 使用文档：$SCRIPT_DIR/AUTOMATION_README.md"
    echo ""
}

# 主函数
main() {
    echo -e "${GREEN}Authelia 自动化脚本演示${NC}"
    echo -e "${BLUE}版本: 1.0.0${NC}"
    echo ""
    echo "本演示将展示如何使用创建的自动化脚本来管理Authelia"
    echo ""
    
    # 检查脚本是否存在
    if [ ! -f "$AUTOMATION_SCRIPT" ]; then
        log_error "自动化脚本不存在: $AUTOMATION_SCRIPT"
        exit 1
    fi
    
    if [ ! -f "$QUICK_SETUP_SCRIPT" ]; then
        log_error "快速配置脚本不存在: $QUICK_SETUP_SCRIPT"
        exit 1
    fi
    
    log_success "脚本文件检查通过"
    echo ""
    
    # 运行演示
    demo_quick_setup
    echo ""
    
    demo_step_by_step
    echo ""
    
    demo_management
    echo ""
    
    demo_real_test
    echo ""
    
    show_summary
    
    echo -e "${GREEN}演示完成！${NC}"
    echo ""
    echo -e "${YELLOW}下一步：${NC}"
    echo "1. 阅读详细文档：$SCRIPT_DIR/AUTOMATION_README.md"
    echo "2. 根据实际需求配置Authelia"
    echo "3. 测试配置是否正确"
    echo ""
}

# 设置中断处理
trap 'echo -e "${RED}演示被中断！${NC}"; exit 1' INT

# 执行主函数
main "$@"
