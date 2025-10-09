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

# 日志函数
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${PURPLE}[STEP]${NC} $1"; }

# 全局变量
PV_NAME=""
POD_NAME=""
STORAGE_DIR=""
NEW_POD_NAME=""
MINIO_PASSWORD=""
MINIO_ROOT_USER="minioadmin"
MINIO_HOST=""
MINIO_PORT=""
source_dir="/home/dump/minio"

# 打印横幅
print_banner() {
    echo -e "${GREEN}"
    echo "===================================================================="
    echo "                  MINIO数据导入脚本"
    echo "                 Euler Copilot 项目专用"
    echo "===================================================================="
    echo -e "${NC}"
}

print_completion_banner() {
    echo -e "${GREEN}"
    echo "===================================================================="
    echo "                  MINIO数据导入已完成！"
    echo "===================================================================="
    echo -e "${NC}"
}

# 用户确认
confirm_execution() {
    echo -e "${YELLOW}警告: 此操作将清空现有MinIO数据并导入新数据！${NC}"
    read -p "确认执行MinIO数据导入操作？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "操作已取消"
        exit 0
    fi
}

# 清除颜色代码和特殊字符
clean_output() {
    echo "$1" | sed -r "s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g" | tr -d '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
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

# 检查前置条件
check_prerequisites() {
    log_step "检查前置条件..."
    
    # 检查kubectl是否可用
    kubectl cluster-info &> /dev/null
    check_command "kubectl连接正常" "无法连接到Kubernetes集群"
    
    # 检查命名空间是否存在
    if ! kubectl get namespace euler-copilot &> /dev/null; then
        log_error "命名空间 euler-copilot 不存在"
        exit 1
    fi
    log_success "命名空间 euler-copilot 存在"
}

# 获取K8s资源信息
get_kubernetes_resources() {
    log_step "获取Kubernetes资源信息..."
    
    # 获取PV名称
    PV_NAME=$(kubectl get pv -n euler-copilot | grep minio | awk '{print $1}')
    if [ -z "$PV_NAME" ]; then
        log_error "未找到MinIO的PV"
        exit 1
    fi
    log_info "PV名称: $PV_NAME"
    
    # 获取Pod名称
    POD_NAME=$(kubectl get pods -n euler-copilot | grep minio | grep Running | awk '{print $1}')
    POD_NAME=$(clean_output "$POD_NAME")
    if [ -z "$POD_NAME" ]; then
        log_error "未找到运行的MinIO Pod"
        exit 1
    fi
    log_info "Pod名称: $POD_NAME"
    
    # 设置存储目录
    STORAGE_DIR="/var/lib/rancher/k3s/storage/${PV_NAME}_euler-copilot_minio-storage/"
    log_info "存储目录: $STORAGE_DIR"
}

# 复制数据
copy_data() {
    log_step "复制数据..."
    
    if [ -d "$source_dir" ]; then
        # 检查源数据
        local source_count=$(find "$source_dir" -type f 2>/dev/null | wc -l)
        if [ "$source_count" -eq 0 ]; then
            log_warning "源目录为空，跳过复制"
            return 0
        fi
        
        log_info "源目录文件数: $source_count"
        cp -r "$source_dir"/* "$STORAGE_DIR"
        check_command "数据复制完成" "数据复制失败"
        
        # 验证复制结果
        local new_count=$(find "$STORAGE_DIR" -type f 2>/dev/null | wc -l)
        log_info "复制后文件数量: $new_count"
        
        if [ "$source_count" -eq "$new_count" ]; then
            log_success "文件数量验证成功"
        else
            log_warning "文件数量不一致: 源=$source_count, 目标=$new_count"
        fi
    else
        log_error "源目录 $source_dir 不存在"
        exit 1
    fi
}

# 重启Pod
restart_pod() {
    log_step "重启Pod..."
    
    kubectl delete pod "$POD_NAME" -n euler-copilot
    check_command "Pod删除命令执行成功" "Pod删除失败"
    
    # 等待Pod重启
    log_info "等待Pod重启..."
    local timeout=60
    local counter=0
    
    while [ $counter -lt $timeout ]; do
        NEW_POD_NAME=$(kubectl get pods -n euler-copilot | grep minio | grep Running | awk '{print $1}')
        NEW_POD_NAME=$(clean_output "$NEW_POD_NAME")
        
        if [ -n "$NEW_POD_NAME" ]; then
            log_success "Pod重启成功: $NEW_POD_NAME"
            return 0
        fi
        
        counter=$((counter + 5))
        sleep 5
        echo -n "."
    done
    
    log_error "Pod未在指定时间内重启成功"
    return 1
}

# 获取MinIO配置
get_minio_config() {
    log_step "获取MinIO配置..."
    
    MINIO_PASSWORD=$(kubectl get secret euler-copilot-database -n euler-copilot -o jsonpath='{.data.minio-password}' 2>/dev/null | base64 --decode)
    if [ $? -ne 0 ] || [ -z "$MINIO_PASSWORD" ]; then
        log_error "获取MinIO密码失败"
        exit 1
    fi
    
    MINIO_HOST=$(kubectl get svc -n euler-copilot | grep minio-service | awk '{print $3}')
    MINIO_PORT=$(kubectl get svc -n euler-copilot | grep minio-service | awk '{split($5, a, "/"); print a[1]}')
    
    log_info "MinIO配置:"
    log_info "  主机: $MINIO_HOST"
    log_info "  端口: $MINIO_PORT"
    log_info "  用户: $MINIO_ROOT_USER"
}

# 验证MinIO数据
verify_minio_data() {
    log_step "验证MinIO数据..."
    
    # 设置mc客户端
    kubectl exec -it "$NEW_POD_NAME" -n euler-copilot -- mc alias set myminio "http://${MINIO_HOST}:${MINIO_PORT}" "$MINIO_ROOT_USER" "$MINIO_PASSWORD"
    check_command "MinIO客户端设置成功" "MinIO客户端设置失败"
    
    # 列出buckets
    log_info "MinIO Buckets列表:"
    kubectl exec -it "$NEW_POD_NAME" -n euler-copilot -- mc ls myminio
    if [ $? -eq 0 ]; then
        log_success "MinIO连接正常"
    else
        log_error "MinIO连接失败"
        exit 1
    fi
    
    # 检查具体bucket内容
    log_info "检查witchaind-doc bucket:"
    kubectl exec -it "$NEW_POD_NAME" -n euler-copilot -- mc ls myminio/witchaind-doc
    if [ $? -eq 0 ]; then
        log_success "witchaind-doc bucket访问成功"
    else
        log_warning "witchaind-doc bucket不存在或为空"
    fi
}

# 主函数
main() {
    print_banner
    confirm_execution
    
    # 执行各个步骤
    check_prerequisites
    get_kubernetes_resources
    copy_data
    restart_pod
    get_minio_config
    verify_minio_data
    
    print_completion_banner
    log_success "MinIO数据导入流程已全部完成"
    log_info "请验证业务功能是否正常"
}

# 执行主函数
main "$@"
