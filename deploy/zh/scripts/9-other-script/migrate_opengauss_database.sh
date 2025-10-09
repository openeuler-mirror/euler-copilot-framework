#!/bin/bash

# OpenGauss数据库导入脚本
# 描述：用于Euler Copilot项目的数据库数据导入

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
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] 警告: $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] 错误: $1${NC}" >&2
    exit 1
}

step() {
    echo -e "${PURPLE}[$(date '+%Y-%m-%d %H:%M:%S')] === $1 ===${NC}"
}

# 配置变量
NAMESPACE="euler-copilot"
SECRET_NAME="euler-copilot-database"
PASSWORD_KEY="gauss-password"
BACKUP_FILE="/home/dump/opengauss/opengauss.sql"
POD_BACKUP_PATH="/home/omm/opengauss.sql"

# 检查必要工具
check_dependencies() {
    step "检查必要工具"
    command -v kubectl >/dev/null 2>&1 || error "kubectl 未安装"
    command -v base64 >/dev/null 2>&1 || error "base64 未安装"
    log "依赖检查通过"
}

# 获取数据库密码
get_database_password() {
    step "获取数据库密码"
    PASSWORD=$(kubectl get secret $SECRET_NAME -n $NAMESPACE -o jsonpath="{.data.$PASSWORD_KEY}" 2>/dev/null | base64 --decode)
    
    if [ -z "$PASSWORD" ]; then
        error "无法获取数据库密码，请检查secret是否存在"
    fi
    log "密码获取成功"
}

# 获取OpenGauss Pod名称
get_opengauss_pod() {
    step "查找OpenGauss Pod"
    POD_NAME=$(kubectl get pod -n $NAMESPACE 2>/dev/null | grep opengauss | grep Running | awk '{print $1}')
    
    if [ -z "$POD_NAME" ]; then
        error "未找到运行的OpenGauss Pod"
    fi
    log "找到Pod: $POD_NAME"
}

# 检查备份文件是否存在
check_backup_file() {
    step "检查备份文件"
    if [ ! -f "$BACKUP_FILE" ]; then
        error "备份文件 $BACKUP_FILE 不存在"
    fi
    log "备份文件检查通过: $BACKUP_FILE"
}

# 拷贝备份文件到Pod
copy_backup_to_pod() {
    step "拷贝备份文件到Pod"
    kubectl cp "$BACKUP_FILE" "$POD_NAME:$POD_BACKUP_PATH" -n $NAMESPACE
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- bash -c "chown omm:omm $POD_BACKUP_PATH"
    log "备份文件拷贝完成"
}

# 执行数据库导入
import_database() {
    step "执行数据库导入操作"
    
    info "步骤1: 禁用外键约束..."
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c \
        "gsql -d postgres -U postgres -W '$PASSWORD' -c \"SET session_replication_role = replica;\""
    log "外键约束已禁用"
    
    info "步骤2: 清空表数据..."
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c \
        "gsql -d postgres -U postgres -W '$PASSWORD' -c \"
TRUNCATE TABLE 
    action, team, knowledge_base, document, chunk, document_type, 
    role, role_action, users, task, task_report, team_user, user_role,
    dataset, dataset_doc, image, qa, task_queue, team_message, 
    testcase, testing, user_message
CASCADE;\""
    log "表数据清空完成"
    
    info "步骤3: 导入数据..."
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c \
        "gsql -d postgres -U postgres -f $POD_BACKUP_PATH -W '$PASSWORD'"
    log "数据导入完成"
    
    info "步骤4: 启用外键约束..."
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c \
        "gsql -d postgres -U postgres -W '$PASSWORD' -c \"SET session_replication_role = origin;\""
    log "外键约束已启用"
    
    log "数据库导入操作全部完成"
}

# 清理临时文件
cleanup() {
    step "清理临时文件"
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- rm -f "$POD_BACKUP_PATH" 2>/dev/null || true
    log "清理完成"
}

# 显示横幅
show_banner() {
    echo -e "${PURPLE}"
    echo "================================================================"
    echo "                OpenGauss 数据库导入脚本"
    echo "                Euler Copilot 项目专用"
    echo "================================================================"
    echo -e "${NC}"
}

# 主函数
main() {
    show_banner
    step "开始OpenGauss数据库导入流程"
    
    check_dependencies
    get_database_password
    get_opengauss_pod
    check_backup_file
    copy_backup_to_pod
    import_database
    cleanup
    
    echo -e "${GREEN}"
    echo "================================================================"
    echo "                   OpenGauss数据导入已完成！"
    echo "================================================================"
    echo -e "${NC}"
    
    echo -e "${GREEN}✓ 外键约束已禁用${NC}"
    echo -e "${GREEN}✓ 表数据已清空${NC}"
    echo -e "${GREEN}✓ 新数据已导入${NC}"
    echo -e "${GREEN}✓ 外键约束已重新启用${NC}"
    echo ""
    echo -e "${BLUE}提示: 建议检查应用运行状态以确保数据导入成功。${NC}"
}

# 显示使用说明
usage() {
    show_banner
    echo -e "${YELLOW}用法: $0${NC}"
    echo ""
    echo -e "说明: 该脚本用于导入Euler Copilot项目的OpenGauss数据库数据"
    echo ""
    echo -e "${CYAN}前提条件:${NC}"
    echo -e "  1. kubectl已配置并可访问集群"
    echo -e "  2. opengauss.sql文件存在于当前目录"
    echo -e "  3. 具有足够的集群权限"
    echo ""
    echo -e "${RED}警告: 此操作将清空现有数据库数据并导入新数据！${NC}"
}

# 脚本入口
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
    exit 0
fi

# 修复颜色显示问题
echo -e "${YELLOW}警告: 此操作将清空现有数据库数据并导入新数据！${NC}"

# 方法1：使用临时变量
yellow_text="${YELLOW}确认执行数据库导入操作？(y/N): ${NC}"
read -p "$(echo -e "$yellow_text")" confirm

# 方法2：或者直接使用echo -e（备选方案）
# echo -e "${YELLOW}确认执行数据库导入操作？(y/N): ${NC}\c"
# read confirm

case $confirm in
    [yY] | [yY][eE][sS])
        main
        ;;
    *)
        warning "操作已取消"
        exit 0
        ;;
esac
