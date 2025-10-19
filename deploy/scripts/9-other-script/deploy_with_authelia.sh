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

# 打印帮助信息
print_help() {
    echo -e "${GREEN}用法: $0 [选项]"
    echo -e "选项:"
    echo -e "  --help                      显示帮助信息"
    echo -e "  --authelia_address <地址>   指定Authelia的访问地址（例如：http://myhost:30091）"
    echo -e "  --euler_address <地址>      指定EulerCopilot的访问地址（例如：http://myhost:30080）"
    echo -e ""
    echo -e "示例:"
    echo -e "  $0 --authelia_address http://myhost:30091 --euler_address http://myhost:30080${NC}"
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

# 部署Authelia
deploy_authelia() {
    local arch="$1"
    local authelia_address="$2"
    
    echo -e "${BLUE}==> 部署 Authelia...${NC}"
    
    # 提取域名/IP用于会话配置
    local domain
    domain=$(echo "$authelia_address" | sed -E 's|^https?://([^:/]+).*|\1|')
    
    cd "${CHART_DIR}"
    helm upgrade --install authelia -n euler-copilot ./authelia \
        --set globals.arch="$arch" \
        --set domain.authelia="$authelia_address" \
        --set authelia.config.session.domain="$domain" || {
        echo -e "${RED}Authelia 部署失败！${NC}"
        return 1
    }
    
    echo -e "${GREEN}Authelia 部署完成！${NC}"
}

# 部署EulerCopilot Framework with Authelia
deploy_euler_copilot() {
    local arch="$1"
    local authelia_address="$2"
    local euler_address="$3"
    
    echo -e "${BLUE}==> 部署 EulerCopilot Framework (使用Authelia鉴权)...${NC}"
    
    cd "${CHART_DIR}"
    
    # 这里需要用户提供实际的模型配置
    echo -e "${YELLOW}注意：请确保已正确配置模型相关参数${NC}"
    
    helm upgrade --install euler-copilot -n euler-copilot ./euler_copilot \
        --set globals.arch="$arch" \
        --set login.provider="authelia" \
        --set login.authelia.client_id="euler-copilot" \
        --set login.authelia.client_secret="your-client-secret-here" \
        --set domain.euler_copilot="$euler_address" \
        --set domain.authelia="$authelia_address" \
        --set euler_copilot.sandbox.enabled=true \
        --set models.answer.endpoint="http://localhost:11434" \
        --set models.answer.key="ollama" \
        --set models.answer.name="qwen2.5:14b" \
        --set models.embedding.type="openai" \
        --set models.embedding.endpoint="http://localhost:11434" \
        --set models.embedding.key="ollama" \
        --set models.embedding.name="bge-m3" || {
        echo -e "${RED}EulerCopilot Framework 部署失败！${NC}"
        return 1
    }
    
    echo -e "${GREEN}EulerCopilot Framework 部署完成！${NC}"
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
    
    local authelia_address="${authelia_address:-http://127.0.0.1:30091}"
    local euler_address="${euler_address:-http://127.0.0.1:30080}"
    
    create_namespace || exit 1
    deploy_authelia "$arch" "$authelia_address" || exit 1
    deploy_euler_copilot "$arch" "$authelia_address" "$euler_address" || exit 1
    check_pods_status || {
        echo -e "${RED}部署失败：Pod状态检查未通过！${NC}"
        exit 1
    }

    echo -e "\n${GREEN}========================="
    echo -e "Euler Copilot Framework (Authelia版) 部署完成！"
    echo -e "Authelia 登录地址: $authelia_address"
    echo -e "EulerCopilot 访问地址: $euler_address"
    echo -e "默认Authelia账号: admin/admin123 或 user/user123"
    echo -e "=========================${NC}"
    echo -e "\n${YELLOW}重要提示：${NC}"
    echo -e "1. 生产环境请修改Authelia的默认密码和密钥"
    echo -e "2. 请确保模型服务已正确部署和配置"
    echo -e "3. 首次访问需要通过Authelia进行身份验证"
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help)
                print_help
                exit 0
                ;;
            --authelia_address)
                if [ -n "$2" ]; then
                    authelia_address="$2"
                    shift 2
                else
                    echo -e "${RED}错误：--authelia_address 需要提供一个参数${NC}" >&2
                    exit 1
                fi
                ;;
            --euler_address)
                if [ -n "$2" ]; then
                    euler_address="$2"
                    shift 2
                else
                    echo -e "${RED}错误：--euler_address 需要提供一个参数${NC}" >&2
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
