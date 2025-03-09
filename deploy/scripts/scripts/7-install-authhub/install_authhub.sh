#!/bin/bash

set -eo pipefail

RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
NC='\033[0m'

SCRIPT_PATH="$(
  cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1
  pwd
)/$(basename "${BASH_SOURCE[0]}")"

CHART_DIR="$(
  canonical_path=$(readlink -f "$SCRIPT_PATH" 2>/dev/null || echo "$SCRIPT_PATH")
  dirname "$(dirname "$(dirname "$canonical_path")")"
)/chart"

# 获取系统架构
get_architecture() {
    local arch=$(uname -m)
    case "$arch" in
        x86_64)
            arch="x86"
            ;;
        aarch64)
            arch="arm"
            ;;
        *)
            echo -e "${RED}错误：不支持的架构 $arch${NC}" >&2
            return 1
            ;;
    esac
    echo -e "${GREEN}检测到系统架构：$(uname -m)${NC}" >&2
    echo "$arch"
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

    local RELEASES
    RELEASES=$(helm list -n euler-copilot --short | grep authhub || true)

    if [ -n "$RELEASES" ]; then
        echo -e "${YELLOW}找到以下Helm Release，开始清理...${NC}"
        for release in $RELEASES; do
            echo -e "${BLUE}正在删除Helm Release: ${release}${NC}"
            helm uninstall "$release" -n euler-copilot || echo -e "${RED}删除Helm Release失败，继续执行...${NC}"
        done
    else
        echo -e "${YELLOW}未找到需要清理的Helm Release${NC}"
    fi

    local pvc_name
    pvc_name=$(kubectl get pvc -n euler-copilot | grep 'mysql-pvc' 2>/dev/null || true)

    if [ -n "$pvc_name" ]; then
        echo -e "${YELLOW}找到以下PVC，开始清理...${NC}"
        kubectl delete pvc mysql-pvc -n euler-copilot --force --grace-period=0 || echo -e "${RED}PVC删除失败，继续执行...${NC}"
    else
        echo -e "${YELLOW}未找到需要清理的PVC${NC}"
    fi

    echo -e "${GREEN}资源清理完成${NC}"
}

get_user_input() {
    echo -e "${BLUE}请输入 Authhub 的域名配置（直接回车使用默认值 authhub.eulercopilot.local）：${NC}"
    read -p "Authhub 的前端域名: " authhub_domain

    if [[ -z "$authhub_domain" ]]; then
        authhub_domain="authhub.eulercopilot.local"
        echo -e "${GREEN}使用默认域名：${authhub_domain}${NC}"
    else
        if ! [[ "${authhub_domain}" =~ ^([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$ ]]; then
            echo -e "${RED}错误：输入的AuthHub域名格式不正确${NC}"
            exit 1
        fi
        echo -e "${GREEN}输入域名：${authhub_domain}${NC}"
    fi
}

helm_install() {
    local arch="$1"
    echo -e "${BLUE}==> 进入部署目录...${NC}"
    [ ! -d "${CHART_DIR}" ] && {
        echo -e "${RED}错误：部署目录不存在 ${CHART_DIR} ${NC}"
        return 1
    }
    cd "${CHART_DIR}"

    echo -e "${BLUE}正在安装 authhub...${NC}"
    helm upgrade --install authhub -n euler-copilot ./authhub \
        --set globals.arch="$arch" \
        --set domain.authhub="${authhub_domain}" || {
        echo -e "${RED}Helm 安装 authhub 失败！${NC}"
        return 1
    }
}

check_pods_status() {
    echo -e "${BLUE}==> 等待初始化就绪（30秒）...${NC}" >&2
    sleep 30

    local timeout=300
    local start_time=$(date +%s)

    echo -e "${BLUE}开始监控Pod状态（总超时时间300秒）...${NC}" >&2

    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [ $elapsed -gt $timeout ]; then
            echo -e "${YELLOW}警告：部署超时！请检查以下资源：${NC}" >&2
            kubectl get pods -n euler-copilot -o wide
            echo -e "\n${YELLOW}建议检查：${NC}"
            echo "1. 查看未就绪Pod的日志: kubectl logs -n euler-copilot <pod-name>"
            echo "2. 检查PVC状态: kubectl get pvc -n euler-copilot"
            echo "3. 检查Service状态: kubectl get svc -n euler-copilot"
            return 1
        fi

        local not_running=$(kubectl get pods -n euler-copilot -o jsonpath='{range .items[*]}{.metadata.name} {.status.phase} {.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' \
            | awk '$2 != "Running" || $3 != "True" {print $1 " " $2}')

        if [ -z "$not_running" ]; then
            echo -e "${GREEN}所有Pod已正常运行！${NC}" >&2
            kubectl get pods -n euler-copilot -o wide
            return 0
        else
            echo "等待Pod就绪（已等待 ${elapsed} 秒）..."
            echo "当前未就绪Pod："
            echo "$not_running" | awk '{print "  - " $1 " (" $2 ")"}'
            sleep 10
        fi
    done
}

main() {
    local arch
    arch=$(get_architecture) || exit 1
    create_namespace || exit 1
    delete_pvcs || exit 1
    get_user_input || exit 1
    helm_install "$arch" || exit 1
    check_pods_status || {
        echo -e "${RED}部署失败：Pod状态检查未通过！${NC}"
        exit 1
    }

    echo -e "\n${GREEN}========================="
    echo -e "Authhub 部署完成！"
    echo -e "查看pod状态：kubectl get pod -n euler-copilot"
    echo -e "Authhub登录地址为: https://${authhub_domain}"
    echo -e "默认账号密码: administrator/changeme"
    echo -e "=========================${NC}"
}

trap 'echo -e "${RED}操作被中断！${NC}"; exit 1' INT
main "$@"
