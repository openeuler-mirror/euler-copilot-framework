#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 强制清理鉴权服务相关资源
force_cleanup_auth_services() {
    echo -e "${BLUE}==> 开始强制清理鉴权服务资源...${NC}"
    
    local namespace="euler-copilot"
    
    # 1. 强制删除所有相关的Pod
    echo -e "${YELLOW}步骤1: 强制删除相关Pod...${NC}"
    local pods
    pods=$(kubectl get pods -n "$namespace" | grep -E "(authelia|authhub|mysql)" | awk '{print $1}' || true)
    
    if [ -n "$pods" ]; then
        echo -e "${YELLOW}找到以下Pod，开始强制删除...${NC}"
        echo "$pods"
        
        for pod in $pods; do
            echo -e "${BLUE}强制删除Pod: ${pod}${NC}"
            # 首先尝试正常删除
            kubectl delete pod "$pod" -n "$namespace" --grace-period=0 2>/dev/null || true
            
            # 如果Pod仍然存在，强制删除
            if kubectl get pod "$pod" -n "$namespace" &>/dev/null; then
                echo -e "${YELLOW}正常删除失败，使用强制删除...${NC}"
                kubectl delete pod "$pod" -n "$namespace" --force --grace-period=0 2>/dev/null || true
            fi
            
            # 等待Pod完全删除
            local timeout=30
            local count=0
            while kubectl get pod "$pod" -n "$namespace" &>/dev/null && [ $count -lt $timeout ]; do
                echo -e "${YELLOW}等待Pod ${pod} 删除... (${count}/${timeout})${NC}"
                sleep 1
                ((count++))
            done
            
            if kubectl get pod "$pod" -n "$namespace" &>/dev/null; then
                echo -e "${RED}警告: Pod ${pod} 仍然存在，可能需要手动处理${NC}"
            else
                echo -e "${GREEN}Pod ${pod} 删除成功${NC}"
            fi
        done
    else
        echo -e "${YELLOW}未找到需要删除的Pod${NC}"
    fi
    
    # 2. 删除Helm Release
    echo -e "${YELLOW}步骤2: 删除Helm Release...${NC}"
    local releases
    releases=$(helm list -n "$namespace" --short | grep -E "(authhub|authelia)" || true)
    
    if [ -n "$releases" ]; then
        echo -e "${YELLOW}找到以下Helm Release，开始删除...${NC}"
        echo "$releases"
        
        for release in $releases; do
            echo -e "${BLUE}删除Helm Release: ${release}${NC}"
            helm uninstall "$release" -n "$namespace" || echo -e "${RED}删除Helm Release失败，继续执行...${NC}"
        done
    else
        echo -e "${YELLOW}未找到需要删除的Helm Release${NC}"
    fi
    
    # 3. 强制删除PVC
    echo -e "${YELLOW}步骤3: 强制删除PVC...${NC}"
    local pvcs
    pvcs=$(kubectl get pvc -n "$namespace" | grep -E "(mysql-pvc|authelia.*data)" | awk '{print $1}' || true)
    
    if [ -n "$pvcs" ]; then
        echo -e "${YELLOW}找到以下PVC，开始强制删除...${NC}"
        echo "$pvcs"
        
        for pvc in $pvcs; do
            echo -e "${BLUE}强制删除PVC: ${pvc}${NC}"
            
            # 首先移除finalizers（如果存在）
            kubectl patch pvc "$pvc" -n "$namespace" -p '{"metadata":{"finalizers":null}}' 2>/dev/null || true
            
            # 强制删除PVC
            kubectl delete pvc "$pvc" -n "$namespace" --force --grace-period=0 || echo -e "${RED}PVC删除失败，继续执行...${NC}"
            
            # 验证删除结果
            if kubectl get pvc "$pvc" -n "$namespace" &>/dev/null; then
                echo -e "${RED}警告: PVC ${pvc} 仍然存在${NC}"
            else
                echo -e "${GREEN}PVC ${pvc} 删除成功${NC}"
            fi
        done
    else
        echo -e "${YELLOW}未找到需要删除的PVC${NC}"
    fi
    
    # 4. 删除相关的PV（如果是本地存储）
    echo -e "${YELLOW}步骤4: 检查并删除相关PV...${NC}"
    local pvs
    pvs=$(kubectl get pv | grep -E "(mysql|authelia)" | awk '{print $1}' || true)
    
    if [ -n "$pvs" ]; then
        echo -e "${YELLOW}找到以下PV，开始删除...${NC}"
        echo "$pvs"
        
        for pv in $pvs; do
            echo -e "${BLUE}删除PV: ${pv}${NC}"
            
            # 移除finalizers
            kubectl patch pv "$pv" -p '{"metadata":{"finalizers":null}}' 2>/dev/null || true
            
            # 删除PV
            kubectl delete pv "$pv" --force --grace-period=0 || echo -e "${RED}PV删除失败，继续执行...${NC}"
        done
    else
        echo -e "${YELLOW}未找到需要删除的PV${NC}"
    fi
    
    # 5. 删除相关Secrets
    echo -e "${YELLOW}步骤5: 删除相关Secrets...${NC}"
    local secrets=("authhub-secret" "authelia-secret" "mysql-secret")
    
    for secret in "${secrets[@]}"; do
        if kubectl get secret "$secret" -n "$namespace" &>/dev/null; then
            echo -e "${YELLOW}删除Secret: ${secret}${NC}"
            kubectl delete secret "$secret" -n "$namespace" || echo -e "${RED}删除Secret失败，继续执行...${NC}"
        fi
    done
    
    # 6. 删除相关ConfigMaps
    echo -e "${YELLOW}步骤6: 删除相关ConfigMaps...${NC}"
    local configmaps
    configmaps=$(kubectl get configmap -n "$namespace" | grep -E "(authelia|authhub|mysql)" | awk '{print $1}' || true)
    
    if [ -n "$configmaps" ]; then
        echo -e "${YELLOW}找到以下ConfigMap，开始删除...${NC}"
        echo "$configmaps"
        
        for cm in $configmaps; do
            echo -e "${BLUE}删除ConfigMap: ${cm}${NC}"
            kubectl delete configmap "$cm" -n "$namespace" || echo -e "${RED}删除ConfigMap失败，继续执行...${NC}"
        done
    else
        echo -e "${YELLOW}未找到需要删除的ConfigMap${NC}"
    fi
    
    # 7. 删除相关Services
    echo -e "${YELLOW}步骤7: 删除相关Services...${NC}"
    local services
    services=$(kubectl get svc -n "$namespace" | grep -E "(authelia|authhub|mysql)" | awk '{print $1}' || true)
    
    if [ -n "$services" ]; then
        echo -e "${YELLOW}找到以下Service，开始删除...${NC}"
        echo "$services"
        
        for svc in $services; do
            echo -e "${BLUE}删除Service: ${svc}${NC}"
            kubectl delete svc "$svc" -n "$namespace" || echo -e "${RED}删除Service失败，继续执行...${NC}"
        done
    else
        echo -e "${YELLOW}未找到需要删除的Service${NC}"
    fi
    
    # 8. 最终检查
    echo -e "${YELLOW}步骤8: 最终检查...${NC}"
    
    echo -e "${BLUE}剩余的相关资源:${NC}"
    echo -e "${BLUE}Pods:${NC}"
    kubectl get pods -n "$namespace" | grep -E "(authelia|authhub|mysql)" || echo -e "${GREEN}无相关Pod${NC}"
    
    echo -e "${BLUE}PVCs:${NC}"
    kubectl get pvc -n "$namespace" | grep -E "(mysql-pvc|authelia.*data)" || echo -e "${GREEN}无相关PVC${NC}"
    
    echo -e "${BLUE}Services:${NC}"
    kubectl get svc -n "$namespace" | grep -E "(authelia|authhub|mysql)" || echo -e "${GREEN}无相关Service${NC}"
    
    echo -e "${GREEN}==> 强制清理完成！${NC}"
}

# 显示帮助信息
show_help() {
    echo -e "${BLUE}强制清理鉴权服务脚本${NC}"
    echo -e "${BLUE}用法:${NC}"
    echo -e "  $0 [选项]"
    echo -e ""
    echo -e "${BLUE}选项:${NC}"
    echo -e "  -h, --help     显示此帮助信息"
    echo -e "  -f, --force    强制清理（跳过确认）"
    echo -e ""
    echo -e "${BLUE}说明:${NC}"
    echo -e "  此脚本将强制删除所有鉴权服务相关资源，包括："
    echo -e "  - Pods (authelia, authhub, mysql)"
    echo -e "  - Helm Releases"
    echo -e "  - PVCs 和 PVs"
    echo -e "  - Secrets 和 ConfigMaps"
    echo -e "  - Services"
}

# 确认操作
confirm_cleanup() {
    if [ "$FORCE" = "true" ]; then
        return 0
    fi
    
    echo -e "${RED}警告: 此操作将强制删除所有鉴权服务相关资源！${NC}"
    echo -e "${YELLOW}这包括所有数据和配置，操作不可逆！${NC}"
    echo -e ""
    read -p "确定要继续吗？(输入 'yes' 确认): " confirm
    
    if [ "$confirm" != "yes" ]; then
        echo -e "${YELLOW}操作已取消${NC}"
        exit 0
    fi
}

# 主函数
main() {
    local FORCE=false
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -f|--force)
                FORCE=true
                shift
                ;;
            *)
                echo -e "${RED}未知参数: $1${NC}"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 检查kubectl命令
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}错误: kubectl 命令未找到${NC}"
        exit 1
    fi
    
    # 检查helm命令
    if ! command -v helm &> /dev/null; then
        echo -e "${RED}错误: helm 命令未找到${NC}"
        exit 1
    fi
    
    # 确认操作
    confirm_cleanup
    
    # 执行清理
    force_cleanup_auth_services
}

# 设置错误处理
set -e
trap 'echo -e "${RED}脚本执行出错！${NC}"; exit 1' ERR

# 执行主函数
main "$@"
