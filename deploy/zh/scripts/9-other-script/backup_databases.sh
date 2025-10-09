#!/bin/bash
set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 备份目录
BACKUP_BASE="/home/dump"
MYSQL_BACKUP_DIR="$BACKUP_BASE/mysql"
OPENGAUSS_BACKUP_DIR="$BACKUP_BASE/opengauss"
MINIO_BACKUP_DIR="$BACKUP_BASE/minio"
OPENGAUSS_DATA_PATH="/home/omm/opengauss.sql"
MYSQL_DATA_PATH="/home/mysql.sql"
MYSQL_USER="authhub"
MYSQL_DB_NAME="oauth2"
MYSQL_TABLE_NAME="user"
GS_USERNAME="postgres"
GS_DB="postgres"



# 时间戳函数
timestamp() {
    echo -n "$(date '+%Y-%m-%d %H:%M:%S')"
}

# 日志函数
log_info() {
    echo -e "$(timestamp) ${BLUE}=== $1 ${NC}"
}

log_success() {
    echo -e "$(timestamp) ${GREEN}$1${NC}"
}

log_warning() {
    echo -e "$(timestamp) ${YELLOW}$1${NC}"
}

log_error() {
    echo -e "$(timestamp) ${RED}$1${NC}"
}

log_step() {
    echo -e "$(timestamp) ${PURPLE} $1 ${NC}"
}

# 打印横幅
print_banner() {
    echo -e "${GREEN}"
    echo "================================================================"
    echo "                  Euler Copilot 数据备份脚本"
    echo "                     MySQL + OpenGauss + MinIO"
    echo "================================================================"
    echo -e "${NC}"
}

print_completion_banner() {
    echo -e "${GREEN}"
    echo "================================================================"
    echo "             MySQL + OpenGauss + MinIO 数据备份已完成！"
    echo "================================================================"
    echo -e "${NC}"
}

# 检查命令执行结果
check_command() {
    if [ $? -eq 0 ]; then
        log_success "$1"
    else
        log_error "$2"
        exit 1
    fi
}

# 创建备份目录
create_backup_directories() {
    log_step "创建备份目录"
    
    mkdir -p "$MYSQL_BACKUP_DIR" "$OPENGAUSS_BACKUP_DIR" "$MINIO_BACKUP_DIR"
    check_command "备份目录创建完成" "备份目录创建失败"
    
    log_info "MySQL备份目录: $MYSQL_BACKUP_DIR"
    log_info "OpenGauss备份目录: $OPENGAUSS_BACKUP_DIR"
    log_info "MinIO备份目录: $MINIO_BACKUP_DIR"
}

# 备份MySQL数据
backup_mysql() {
    log_step "开始备份MySQL数据"
    
    # 获取MySQL Pod名称
    log_info "查找MySQL Pod..."
    local pod_name=$(kubectl get pod -n euler-copilot | grep mysql | awk '{print $1}')
    if [ -z "$pod_name" ]; then
        log_error "未找到MySQL Pod"
        return 1
    fi
    log_success "找到Pod: $pod_name"
    
    # 获取MySQL密码
    log_info "获取MySQL密码..."
    local mysql_password=$(kubectl get secret authhub-secret -n euler-copilot -o jsonpath='{.data.mysql-password}' | base64 --decode)
    if [ -z "$mysql_password" ]; then
        log_error "获取MySQL密码失败"
        return 1
    fi
    log_success "密码获取成功"
    
    # 导出user表
    log_info "导出user表数据..."
    kubectl exec $pod_name -n euler-copilot -- bash -c "mysqldump -u${MYSQL_USER} -p${mysql_password} --no-tablespaces ${MYSQL_DB_NAME} ${MYSQL_TABLE_NAME} > ${MYSQL_DATA_PATH}"
    check_command "user表导出完成" "user表导出失败"
    
    # 拷贝备份文件到本地
    log_info "拷贝备份文件到本地..."
    kubectl cp $pod_name:${MYSQL_DATA_PATH} $MYSQL_BACKUP_DIR/mysql.sql -n euler-copilot
    check_command "MySQL备份文件拷贝完成" "MySQL备份文件拷贝失败"
    
    # 验证备份文件
    if [ -f "$MYSQL_BACKUP_DIR/mysql.sql" ]; then
        local file_size=$(du -h "$MYSQL_BACKUP_DIR/mysql.sql" | cut -f1)
        log_success "MySQL备份完成，文件大小: $file_size"
    else
        log_error "MySQL备份文件未找到"
        return 1
    fi
}

# 备份OpenGauss数据
backup_opengauss() {
    log_step "开始备份OpenGauss数据"
    
    # 获取OpenGauss Pod名称
    log_info "查找OpenGauss Pod..."
    local pod_name=$(kubectl get pod -n euler-copilot | grep opengauss | awk '{print $1}')
    if [ -z "$pod_name" ]; then
        log_error "未找到OpenGauss Pod"
        return 1
    fi
    log_success "找到Pod: $pod_name"
    
    # 获取OpenGauss密码
    log_info "获取OpenGauss密码..."
    local gauss_password=$(kubectl get secret euler-copilot-database -n euler-copilot -o jsonpath='{.data.gauss-password}' | base64 --decode)
    if [ -z "$gauss_password" ]; then
        log_error "获取OpenGauss密码失败"
        return 1
    fi
    log_success "密码获取成功"
    
    # 导出数据库
    log_info "导出OpenGauss数据库..."
    kubectl exec -it "$pod_name" -n euler-copilot -- /bin/sh -c "su - omm -c 'source ~/.bashrc && gs_dump -U ${GS_USERNAME} -f ${OPENGAUSS_DATA_PATH} -p 5432 ${GS_DB} -F p -W \"${gauss_password}\"'"
    check_command "OpenGauss数据库导出完成" "OpenGauss数据库导出失败"
    
    # 拷贝备份文件到本地
    log_info "拷贝备份文件到本地..."
    kubectl cp $pod_name:${OPENGAUSS_DATA_PATH} $OPENGAUSS_BACKUP_DIR/opengauss.sql -n euler-copilot
    check_command "OpenGauss备份文件拷贝完成" "OpenGauss备份文件拷贝失败"
    
    # 验证备份文件
    if [ -f "$OPENGAUSS_BACKUP_DIR/opengauss.sql" ]; then
        local file_size=$(du -h "$OPENGAUSS_BACKUP_DIR/opengauss.sql" | cut -f1)
        log_success "OpenGauss备份完成，文件大小: $file_size"
    else
        log_error "OpenGauss备份文件未找到"
        return 1
    fi
}

# 备份MinIO数据
backup_minio() {
    log_step "开始备份MinIO数据"
    
    # 获取PV名称
    log_info "查找MinIO PV..."
    local pv_name=$(kubectl get pv -n euler-copilot | grep minio | awk '{print $1}')
    if [ -z "$pv_name" ]; then
        log_error "未找到MinIO PV"
        return 1
    fi
    log_success "找到PV: $pv_name"
    
    # MinIO数据目录
    local minio_storage_dir="/var/lib/rancher/k3s/storage/${pv_name}_euler-copilot_minio-storage/"
    
    # 检查源目录是否存在
    if [ ! -d "$minio_storage_dir" ]; then
        log_error "MinIO存储目录不存在: $minio_storage_dir"
        return 1
    fi
    
    # 备份MinIO数据
    log_info "开始备份MinIO数据..."
    cp -r "$minio_storage_dir"* "$MINIO_BACKUP_DIR"/
    check_command "MinIO数据备份完成" "MinIO数据备份失败"
    
    # 验证备份
    local source_count=$(find "$minio_storage_dir" -type f 2>/dev/null | wc -l)
    local backup_count=$(find "$MINIO_BACKUP_DIR" -type f 2>/dev/null | wc -l)
    
    log_info "源文件数: $source_count, 备份文件数: $backup_count"
    
    if [ "$source_count" -eq "$backup_count" ]; then
        log_success "MinIO备份验证成功"
    else
        log_warning "文件数量不一致，但备份已完成"
    fi
}

# 显示备份摘要
show_backup_summary() {
    log_step "备份摘要"
    
    echo -e "${CYAN}"
    echo "备份位置: $BACKUP_BASE"
    echo "----------------------------------------"
    
    # MySQL备份信息
    if [ -f "$MYSQL_BACKUP_DIR/mysql.sql" ]; then
        local mysql_size=$(du -h "$MYSQL_BACKUP_DIR/mysql.sql" | cut -f1)
        echo "MySQL:    $MYSQL_BACKUP_DIR/mysql.sql ($mysql_size)"
    else
        echo "MySQL:    备份失败"
    fi
    
    # OpenGauss备份信息
    if [ -f "$OPENGAUSS_BACKUP_DIR/opengauss.sql" ]; then
        local gauss_size=$(du -h "$OPENGAUSS_BACKUP_DIR/opengauss.sql" | cut -f1)
        echo "OpenGauss: $OPENGAUSS_BACKUP_DIR/opengauss.sql ($gauss_size)"
    else
        echo "OpenGauss: 备份失败"
    fi
    
    # MinIO备份信息
    if [ -d "$MINIO_BACKUP_DIR" ]; then
        local minio_size=$(du -sh "$MINIO_BACKUP_DIR" 2>/dev/null | cut -f1 || echo "未知")
        local minio_count=$(find "$MINIO_BACKUP_DIR" -type f 2>/dev/null | wc -l)
        echo "MinIO:    $MINIO_BACKUP_DIR/ ($minio_size, $minio_count 个文件)"
    else
        echo "MinIO:    备份失败"
    fi
    echo -e "${NC}"
}

# 主函数
main() {
    print_banner
    
    log_step "开始数据备份流程"
    
    # 创建备份目录
    create_backup_directories
    
    # 备份MySQL
    if backup_mysql; then
        log_success "MySQL备份成功"
    else
        log_error "MySQL备份失败"
    fi
    
    # 备份OpenGauss
    if backup_opengauss; then
        log_success "OpenGauss备份成功"
    else
        log_error "OpenGauss备份失败"
    fi
    
    # 备份MinIO
    if backup_minio; then
        log_success "MinIO备份成功"
    else
        log_error "MinIO备份失败"
    fi
    
    # 显示备份摘要
    show_backup_summary
    
    print_completion_banner
    log_success "数据备份流程已完成"
}

# 执行主函数
main "$@"
