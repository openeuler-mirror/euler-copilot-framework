#!/bin/bash

# MySQL数据库恢复脚本
# 描述：用于Euler Copilot项目的MySQL数据库恢复

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 打印函数
print_color() {
    local color=$1
    shift
    echo -e "${color}$*${NC}"
}

log() {
    print_color "${GREEN}" "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

info() {
    print_color "${BLUE}" "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

warning() {
    print_color "${YELLOW}" "[$(date '+%Y-%m-%d %H:%M:%S')] 警告: $1"
}

error() {
    print_color "${RED}" "[$(date '+%Y-%m-%d %H:%M:%S')] 错误: $1" >&2
    exit 1
}

step() {
    echo
    print_color "${PURPLE}" "[$(date '+%Y-%m-%d %H:%M:%S')] === $1 ==="
}

# 配置变量
NAMESPACE="euler-copilot"
SECRET_NAME="authhub-secret"
PASSWORD_KEY="mysql-password"
DB_USER="authhub"
DB_NAME="oauth2"
BACKUP_FILE="/home/dump/mysql/mysql.sql"
POD_BACKUP_PATH="/home/mysql.sql"

# 显示横幅
show_banner() {
    echo
    print_color "${PURPLE}" "================================================"
    print_color "${PURPLE}" "            MySQL 数据库恢复脚本"
    print_color "${PURPLE}" "            Euler Copilot 项目专用"
    print_color "${PURPLE}" "================================================"
    echo
}

# 检查必要工具
check_dependencies() {
    step "检查必要工具"
    command -v kubectl >/dev/null 2>&1 || error "kubectl 未安装"
    command -v base64 >/dev/null 2>&1 || error "base64 未安装"
    log "依赖检查通过"
}

# 获取MySQL Pod名称
get_mysql_pod() {
    step "查找MySQL Pod"
    POD_NAME=$(kubectl get pod -n $NAMESPACE 2>/dev/null | grep mysql | grep Running | awk '{print $1}')
    
    if [ -z "$POD_NAME" ]; then
        error "未找到运行的MySQL Pod"
    fi
    log "找到Pod: $POD_NAME"
}

# 获取MySQL密码
get_mysql_password() {
    step "获取MySQL密码"
    MYSQL_PASSWORD=$(kubectl get secret $SECRET_NAME -n $NAMESPACE -o jsonpath="{.data.$PASSWORD_KEY}" 2>/dev/null | base64 --decode)
    
    if [ -z "$MYSQL_PASSWORD" ]; then
        error "无法获取MySQL密码，请检查secret是否存在"
    fi
    log "密码获取成功"
}

# 检查备份文件是否存在
check_backup_file() {
    step "检查备份文件"
    if [ ! -f "$BACKUP_FILE" ]; then
        error "备份文件 $BACKUP_FILE 不存在"
    fi
    
    # 显示文件信息
    local file_size=$(du -h "$BACKUP_FILE" | cut -f1)
    local file_lines=$(wc -l < "$BACKUP_FILE" 2>/dev/null || echo "未知")
    info "文件路径: $BACKUP_FILE"
    info "文件大小: $file_size"
    info "文件行数: $file_lines"
    
    log "备份文件检查通过"
}

# 拷贝备份文件到Pod
copy_backup_to_pod() {
    step "拷贝备份文件到Pod"
    info "从本地拷贝到Pod: $BACKUP_FILE -> $POD_NAME:$POD_BACKUP_PATH"
    
    kubectl cp "$BACKUP_FILE" "$POD_NAME:$POD_BACKUP_PATH" -n $NAMESPACE
    
    if [ $? -eq 0 ]; then
        log "备份文件拷贝完成"
    else
        error "文件拷贝失败"
    fi
}

# 验证数据库连接
test_database_connection() {
    step "测试数据库连接"
    info "测试用户 $DB_USER 连接到数据库 $DB_NAME"
    
    kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
        mysql -u$DB_USER -p'$MYSQL_PASSWORD' -e 'SELECT 1;' $DB_NAME 2>/dev/null
    " >/dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        log "数据库连接测试成功"
    else
        error "数据库连接失败，请检查密码和网络连接"
    fi
}

# 执行数据库恢复
restore_database() {
    step "执行数据库恢复"
    warning "此操作将覆盖现有数据库数据！"
    
    info "开始恢复数据库..."
    kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
        mysql -u$DB_USER -p'$MYSQL_PASSWORD' $DB_NAME < $POD_BACKUP_PATH
    "
    
    local restore_status=$?
    
    if [ $restore_status -eq 0 ]; then
        log "数据库恢复成功"
    else
        error "数据库恢复失败，退出码: $restore_status"
    fi
}

# 验证恢复结果
verify_restore() {
    step "验证恢复结果"
    info "检查数据库表信息..."
    
    local table_count=$(kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
        mysql -u$DB_USER -p'$MYSQL_PASSWORD' -N -e \\
        \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '$DB_NAME';\" 2>/dev/null
    " 2>/dev/null)
    
    if [ -n "$table_count" ] && [ "$table_count" -gt 0 ]; then
        log "恢复验证成功，数据库包含 $table_count 张表"
        
        # 显示部分表名
        info "数据库表列表:"
        kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
            mysql -u$DB_USER -p'$MYSQL_PASSWORD' -e \\
            \"SELECT table_name FROM information_schema.tables WHERE table_schema = '$DB_NAME' LIMIT 10;\" 2>/dev/null
        " 2>/dev/null
    else
        warning "无法获取表信息，但恢复操作已完成"
    fi
}

# 清理临时文件
cleanup() {
    step "清理临时文件"
    info "删除Pod内的备份文件: $POD_BACKUP_PATH"
    
    kubectl exec $POD_NAME -n $NAMESPACE -- rm -f "$POD_BACKUP_PATH" 2>/dev/null || true
    
    log "清理完成"
}

# 显示使用说明
usage() {
    show_banner
    print_color "${YELLOW}" "用法: $0"
    echo
    print_color "${CYAN}" "说明: 该脚本用于恢复Euler Copilot项目的MySQL数据库"
    echo
    print_color "${CYAN}" "前提条件:"
    print_color "${WHITE}" "  1. kubectl已配置并可访问集群"
    print_color "${WHITE}" "  2. mysql.sql文件存在于当前目录"
    print_color "${WHITE}" "  3. 具有足够的集群权限"
    echo
    print_color "${RED}" "警告: 此操作将覆盖现有数据库数据！"
    echo
}

# 确认操作
confirm_operation() {
    print_color "${YELLOW}" "警告: 此操作将清空现有数据库数据并导入新数据！"
    echo
    read -p "$(print_color "${YELLOW}" "确认执行数据库恢复操作？(y/N): ")" confirm
    case $confirm in
        [yY] | [yY][eE][sS])
            return 0
            ;;
        *)
            warning "操作已取消"
            exit 0
            ;;
    esac
}

# 主函数
main() {
    show_banner
    step "开始MySQL数据库恢复流程"
    
    check_dependencies
    get_mysql_pod
    get_mysql_password
    check_backup_file
    test_database_connection
    confirm_operation
    copy_backup_to_pod
    restore_database
    verify_restore
    cleanup
    
    echo
    print_color "${GREEN}" "================================================"
    print_color "${GREEN}" "           Mysql数据恢复已完成！"
    print_color "${GREEN}" "================================================"
    echo
    print_color "${GREEN}" "✓ 备份文件检查完成"
    print_color "${GREEN}" "✓ 数据库连接测试通过"
    print_color "${GREEN}" "✓ 数据恢复执行成功"
    print_color "${GREEN}" "✓ 临时文件清理完成"
    echo
    print_color "${BLUE}" "提示: 建议检查应用运行状态以确保数据恢复成功。"
}

# 脚本入口
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
    exit 0
fi

main
