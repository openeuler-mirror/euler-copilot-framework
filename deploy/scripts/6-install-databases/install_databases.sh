#!/bin/bash
set -eo pipefail

RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
NC='\033[0m'


chart_dir="/home/euler-copilot-framework/deploy/chart"

# 获取系统架构
get_architecture() {
    arch=$(uname -m)
    case "$arch" in
        x86_64)
            arch="x86_64"
            ;;
        aarch64)
            arch="aarch64"
            ;;
        *)
            echo -e "${RED}错误：不支持的架构 $arch${NC}"
            exit 1
            ;;
    esac
    echo -e "${GREEN}检测到系统架构：$arch${NC}"
}

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


delete_pvcs() {
    echo -e "${BLUE}==> 清理现有资源...${NC}"

    local helm_releases
    helm_releases=$(helm list -n euler-copilot -q --filter '^databases' 2>/dev/null || true)

    if [ -n "$helm_releases" ]; then
        echo -e "${YELLOW}找到以下Helm Release，开始清理...${NC}"
        while IFS= read -r release; do
            echo -e "${BLUE}正在删除Helm Release: ${release}${NC}"
            if ! helm uninstall "$release" -n euler-copilot --wait --timeout 2m; then
                echo -e "${RED}错误：删除Helm Release ${release} 失败！${NC}" >&2
                return 1
            fi
        done <<< "$helm_releases"
    else
        echo -e "${YELLOW}未找到需要清理的Helm Release${NC}"
    fi

    local pvc_list
    pvc_list=$(kubectl get pvc -n euler-copilot -o jsonpath='{.items[*].metadata.name}' 2>/dev/null | tr ' ' '\n' | grep -v '^mysql-pvc$' || true)

    if [ -n "$pvc_list" ]; then
        echo -e "${YELLOW}找到以下PVC，开始清理...${NC}"
        while IFS= read -r pvc; do
            echo -e "${BLUE}正在删除PVC: $pvc${NC}"
            if ! kubectl delete pvc "$pvc" -n euler-copilot --force --grace-period=0; then
                echo -e "${RED}错误：删除PVC $pvc 失败！${NC}" >&2
                return 1
            fi
        done <<< "$pvc_list"
    else
        echo -e "${YELLOW}未找到需要清理的PVC${NC}"
    fi

    echo -e "${BLUE}等待资源清理完成（10秒）...${NC}"
    sleep 10

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
    helm upgrade --install databases --set globals.arch=$arch -n euler-copilot ./databases || {
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
    get_architecture
    create_namespace
    delete_pvcs
    helm_install
    check_pods_status

    echo -e "\n${GREEN}========================="
    echo "数据库部署完成！"
    echo -e "=========================${NC}"
}

trap 'echo -e "${RED}操作被中断！${NC}"; exit 1' INT
main "$@"
