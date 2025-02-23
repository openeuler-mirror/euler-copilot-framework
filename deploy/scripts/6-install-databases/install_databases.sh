#!/bin/bash
set -eo pipefail

RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
NC='\033[0m'


chart_dir="/home/euler-copilot-framework/deploy/chart"

create_namespace() {
    echo -e "${BLUE}==> 检查命名空间 euler-copilot...${NC}"
    if ! kubectl get namespace euler-copilot &> /dev/null; then
        kubectl create namespace euler-copilot || {
            echo -e "${RED}命名空间创建失败！${NC}"
            return 1
        }
        echo -e "${GREEN}命名空间创建成功${NC}"
    else
        echo -e "${YELLOW}命名空间已存在，跳过创建${NC}"
    fi
}


# 删除PVC和Helm Release
delete_pvcs() {
    echo -e "${BLUE}==> 清理现有资源...${NC}"
    
    # 获取Helm Release列表
    local RELEASES
    RELEASES=$(helm list -n euler-copilot --short | grep databases || true)
    
    # 删除所有关联的Helm Release
    if [ -n "$RELEASES" ]; then
        echo -e "${YELLOW}找到以下Helm Release，开始清理...${NC}"
        for release in $RELEASES; do
            echo -e "${BLUE}正在删除Helm Release: ${release}${NC}"
            helm uninstall "$release" -n euler-copilot || echo -e "${RED}删除Helm Release失败，继续执行...${NC}"
        done
    else
        echo -e "${YELLOW}未找到需要清理的Helm Release${NC}"
    fi

    # 获取所有非mysql的PVC列表
    local pvc_list
    pvc_list=$(kubectl get pvc -n euler-copilot -o name | grep -v 'persistentvolumeclaim/mysql-pvc' 2>/dev/null || true)
    
    # 删除PVC
    if [ -n "$pvc_list" ]; then
        echo -e "${YELLOW}找到以下PVC，开始清理...${NC}"
        echo "$pvc_list" | xargs -n 1 kubectl delete -n euler-copilot || echo -e "${RED}PVC删除失败，继续执行...${NC}"
    else
        echo -e "${YELLOW}未找到需要清理的PVC${NC}"
    fi

    echo -e "${GREEN}资源清理完成${NC}"
}

helm_install() {
    echo -e "${BLUE}==> 进入部署目录...${NC}"
    [ ! -d "$chart_dir" ] && {
        echo -e "${RED}错误：部署目录不存在 $chart_dir${NC}"
        return 1
    }
    cd "$chart_dir"

    echo -e "${BLUE}正在安装 databases...${NC}"
    helm install databases -n euler-copilot ./databases || {
        echo -e "${RED}Helm 安装 databases 失败！${NC}"
        return 1
    }
}

check_pods_status() {
    echo -e "${BLUE}==> 等待初始化就绪（30秒）...${NC}"
    sleep 30

    local timeout=300
    local start_time=$(date +%s)

    echo -e "${BLUE}开始监控Pod状态（总超时时间300秒）...${NC}"

    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [ $elapsed -gt $timeout ]; then
            echo -e "${RED}错误：部署超时！${NC}"
            kubectl get pods -n euler-copilot
            return 1
        fi

        local not_running=$(kubectl get pods -n euler-copilot -o jsonpath='{range .items[*]}{.metadata.name} {.status.phase}{"\n"}{end}' | grep -v "Running")

        if [ -z "$not_running" ]; then
            echo -e "${GREEN}所有Pod已正常运行！${NC}"
            kubectl get pods -n euler-copilot
            return 0
        else
            echo "等待Pod就绪（已等待 ${elapsed} 秒）..."
            echo "当前异常Pod："
            echo "$not_running" | awk '{print "  - " $1 " (" $2 ")"}'
            sleep 10
        fi
    done
}

main() {
    create_namespace
    delete_pvcs
    helm_install
    check_pods_status

    echo -e "\n${GREEN}========================="
    echo "Databases 部署完成！"
    echo -e "=========================${NC}"
}

trap 'echo -e "${RED}操作被中断！${NC}"; exit 1' INT
main "$@"
