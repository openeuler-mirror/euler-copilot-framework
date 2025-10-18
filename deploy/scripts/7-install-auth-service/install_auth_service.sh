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

# 全局变量
AUTH_SERVICE=""
AUTH_ADDRESS=""

# 打印帮助信息
print_help() {
    echo -e "${GREEN}用法: $0 [选项]"
    echo -e "选项:"
    echo -e "  --help                      显示帮助信息"
    echo -e "  --service <服务类型>        指定鉴权服务类型 (authhub|authelia)"
    echo -e "  --address <地址>            指定鉴权服务的访问地址"
    echo -e ""
    echo -e "示例:"
    echo -e "  $0 --service authhub --address http://myhost:30081"
    echo -e "  $0 --service authelia --address http://myhost:30091${NC}"
    exit 0
}

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

# 选择鉴权服务
select_auth_service() {
    if [ -n "$AUTH_SERVICE" ]; then
        echo -e "${GREEN}使用参数指定的鉴权服务：$AUTH_SERVICE${NC}"
        return 0
    fi

    echo -e "${BLUE}请选择要部署的鉴权服务：${NC}"
    echo "1) AuthHub"
    echo "2) Authelia"
    echo -n "请输入选项编号（1-2）: "
    
    local choice
    read -r choice
    
    case $choice in
        1)
            AUTH_SERVICE="authhub"
            echo -e "${GREEN}选择了 AuthHub${NC}"
            ;;
        2)
            AUTH_SERVICE="authelia"
            echo -e "${GREEN}选择了 Authelia${NC}"
            ;;
        *)
            echo -e "${RED}无效的选项，请输入1或2${NC}"
            return 1
            ;;
    esac
}

# 获取鉴权服务地址
get_auth_address() {
    local default_address
    
    if [ "$AUTH_SERVICE" = "authhub" ]; then
        default_address="http://127.0.0.1:30081"
    else
        default_address="http://127.0.0.1:30091"
    fi
    
    if [ -n "$AUTH_ADDRESS" ]; then
        echo -e "${GREEN}使用参数指定的鉴权服务地址：$AUTH_ADDRESS${NC}"
        return 0
    fi
    
    echo -e "${BLUE}请输入 ${AUTH_SERVICE} 的访问地址（IP或域名，直接回车使用默认值 ${default_address}）：${NC}"
    read -p "${AUTH_SERVICE} 地址: " AUTH_ADDRESS

    # 处理空输入情况
    if [[ -z "$AUTH_ADDRESS" ]]; then
        AUTH_ADDRESS="$default_address"
        echo -e "${GREEN}使用默认地址：${AUTH_ADDRESS}${NC}"
    else
        echo -e "${GREEN}输入地址：${AUTH_ADDRESS}${NC}"
    fi

    return 0
}

# 清理现有资源
uninstall_auth_services() {
    echo -e "${BLUE}==> 清理现有鉴权服务资源...${NC}"

    local RELEASES
    RELEASES=$(helm list -n euler-copilot --short | grep -E "(authhub|authelia)" || true)

    if [ -n "$RELEASES" ]; then
        echo -e "${YELLOW}找到以下Helm Release，开始清理...${NC}"
        for release in $RELEASES; do
            echo -e "${BLUE}正在删除Helm Release: ${release}${NC}"
            helm uninstall "$release" -n euler-copilot || echo -e "${RED}删除Helm Release失败，继续执行...${NC}"
        done
    else
        echo -e "${YELLOW}未找到需要清理的鉴权服务Helm Release${NC}"
    fi

    # 清理PVC
    local pvc_list
    pvc_list=$(kubectl get pvc -n euler-copilot | grep -E "(mysql-pvc|authelia.*data)" 2>/dev/null || true)

    if [ -n "$pvc_list" ]; then
        echo -e "${YELLOW}找到以下PVC，开始清理...${NC}"
        kubectl get pvc -n euler-copilot | grep -E "(mysql-pvc|authelia.*data)" | awk '{print $1}' | while read pvc; do
            kubectl delete pvc "$pvc" -n euler-copilot --force --grace-period=0 || echo -e "${RED}PVC删除失败，继续执行...${NC}"
        done
    else
        echo -e "${YELLOW}未找到需要清理的PVC${NC}"
    fi

    # 清理Secrets
    local secret_list=("authhub-secret")
    for secret in "${secret_list[@]}"; do
        if kubectl get secret "$secret" -n euler-copilot &>/dev/null; then
            echo -e "${YELLOW}找到Secret: ${secret}，开始清理...${NC}"
            kubectl delete secret "$secret" -n euler-copilot || echo -e "${RED}删除Secret失败，继续执行...${NC}"
        fi
    done

    echo -e "${GREEN}资源清理完成${NC}"
}

# 安装AuthHub
install_authhub() {
    local arch="$1"
    echo -e "${BLUE}==> 安装 AuthHub...${NC}"
    
    helm upgrade --install authhub -n euler-copilot "${CHART_DIR}/authhub" \
        --set globals.arch="$arch" \
        --set domain.authhub="${AUTH_ADDRESS}" || {
        echo -e "${RED}Helm 安装 authhub 失败！${NC}"
        return 1
    }
    
    echo -e "${GREEN}AuthHub 安装完成！${NC}"
    echo -e "${GREEN}登录地址: ${AUTH_ADDRESS}${NC}"
    echo -e "${GREEN}默认账号密码: administrator/changeme${NC}"
}

# 安装Authelia
install_authelia() {
    local arch="$1"
    echo -e "${BLUE}==> 安装 Authelia...${NC}"
    
    # 提取域名/IP用于会话配置
    local domain
    domain=$(echo "$AUTH_ADDRESS" | sed -E 's|^https?://([^:/]+).*|\1|')
    
    helm upgrade --install authelia -n euler-copilot "${CHART_DIR}/authelia" \
        --set globals.arch="$arch" \
        --set domain.authelia="$AUTH_ADDRESS" \
        --set authelia.config.session.domain="$domain" || {
        echo -e "${RED}Helm 安装 authelia 失败！${NC}"
        return 1
    }
    
    echo -e "${GREEN}Authelia 安装完成！${NC}"
    echo -e "${GREEN}登录地址: ${AUTH_ADDRESS}${NC}"
    echo -e "${GREEN}默认管理员账号: admin/admin123${NC}"
    echo -e "${GREEN}默认用户账号: user/user123${NC}"
    echo -e "${YELLOW}重要提示：生产环境请修改默认密码和密钥！${NC}"
}

# Helm安装
helm_install() {
    local arch="$1"
    echo -e "${BLUE}==> 进入部署目录...${NC}"
    [ ! -d "${CHART_DIR}" ] && {
        echo -e "${RED}错误：部署目录不存在 ${CHART_DIR} ${NC}"
        return 1
    }
    cd "${CHART_DIR}"

    case "$AUTH_SERVICE" in
        "authhub")
            install_authhub "$arch"
            ;;
        "authelia")
            install_authelia "$arch"
            ;;
        *)
            echo -e "${RED}错误：未知的鉴权服务类型 $AUTH_SERVICE${NC}"
            return 1
            ;;
    esac
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

deploy() {
    local arch
    arch=$(get_architecture) || exit 1
    create_namespace || exit 1
    uninstall_auth_services || exit 1
    
    # 选择鉴权服务
    select_auth_service || exit 1
    
    # 获取鉴权服务地址
    get_auth_address || exit 1
    
    helm_install "$arch" || exit 1
    check_pods_status || {
        echo -e "${RED}部署失败：Pod状态检查未通过！${NC}"
        exit 1
    }

    echo -e "\n${GREEN}========================="
    echo -e "鉴权服务 ($AUTH_SERVICE) 部署完成！"
    echo -e "查看pod状态：kubectl get pod -n euler-copilot"
    echo -e "服务访问地址: $AUTH_ADDRESS"
    echo -e "=========================${NC}"
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help)
                print_help
                exit 0
                ;;
            --service)
                if [ -n "$2" ] && [[ "$2" =~ ^(authhub|authelia)$ ]]; then
                    AUTH_SERVICE="$2"
                    shift 2
                else
                    echo -e "${RED}错误：--service 需要提供有效参数 (authhub|authelia)${NC}" >&2
                    exit 1
                fi
                ;;
            --address)
                if [ -n "$2" ]; then
                    AUTH_ADDRESS="$2"
                    shift 2
                else
                    echo -e "${RED}错误：--address 需要提供一个参数${NC}" >&2
                    exit 1
                fi
                ;;
            *)
                echo -e "${RED}未知参数: $1${NC}" >&2
                print_help
                exit 1
                ;;
        esac
    done
}

main() {
    parse_args "$@"
    deploy
}

trap 'echo -e "${RED}操作被中断！${NC}"; exit 1' INT
main "$@"
