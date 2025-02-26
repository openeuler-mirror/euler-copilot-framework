#!/bin/bash

set -eo pipefail

# 颜色定义
RED='\e[31m'
GREEN='\e[32m'
YELLOW='\e[33m'
BLUE='\e[34m'
NC='\e[0m' # 恢复默认颜色

DEPLOY_DIR="/home/euler-copilot-framework/deploy"
PLUGINS_DIR="/home/eulercopilot/semantics"

# 获取系统架构
get_architecture() {
    local arch
    arch=$(uname -m)
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
}

# 自动检测业务网口
get_network_ip() {
    echo -e "${BLUE}自动检测业务网络接口 IP 地址...${NC}" >&2
    local timeout=20
    local start_time=$(date +%s)
    local interface=""
    local host=""

    # 查找可用的网络接口
    while [ $(( $(date +%s) - start_time )) -lt $timeout ]; do
        # 获取所有非虚拟接口（排除 lo, docker, veth 等）
        interfaces=$(ip -o link show | awk -F': ' '{print $2}' | grep -vE '^lo$|docker|veth|br-|virbr|tun')

        for intf in $interfaces; do
            # 检查接口状态是否为 UP
            if ip link show "$intf" | grep -q 'state UP'; then
                # 获取 IPv4 地址
                ip_addr=$(ip addr show "$intf" | grep -w inet | awk '{print $2}' | cut -d'/' -f1)
                if [ -n "$ip_addr" ]; then
                    interface=$intf
                    host=$ip_addr
                    break 2 # 跳出两层循环
                fi
            fi
        done
        sleep 1
    done

    if [ -z "$interface" ]; then
        echo -e "${RED}错误：未找到可用的业务网络接口${NC}" >&2
        exit 1
    fi

    echo -e "${GREEN}使用网络接口：${interface}，IP 地址：${host}${NC}" >&2
    echo "$host"
}

get_client_info() {
    # 调用Python脚本并捕获标准输出和标准错误
    output=$(python3 "${DEPLOY_DIR}/scripts/9-other-script/get_client_id_and_secret.py")
    exit_code=$?

    # 检查执行结果
    if [ $exit_code -ne 0 ]; then
        echo -e "${RED}获取客户端凭证失败：${output}${NC}" >&2
        exit 1
    fi

    # 解析输出结果
    client_id=$(echo "$output" | grep "client_id: " | awk '{print $2}')
    client_secret=$(echo "$output" | grep "client_secret: " | awk '{print $2}')

    # 验证结果
    if [ -z "$client_id" ] || [ -z "$client_secret" ]; then
        echo -e "${RED}错误：无法获取有效的客户端凭证${NC}" >&2
        exit 1
    fi

    echo "=============================="
    echo "Client ID:     $client_id"
    echo "Client Secret: $client_secret"
    echo "=============================="
}

get_user_input() {
    # 处理Copilot域名
    echo -e "${BLUE}请输入 EulerCopilot 域名（直接回车使用默认值 www.eulercopilot.local）：${NC}"
    read -p "EulerCopilot 的前端域名: " eulercopilot_domain

    if [[ -z "$eulercopilot_domain" ]]; then
        eulercopilot_domain="www.eulercopilot.local"
        echo -e "${GREEN}使用默认域名：${eulercopilot_domain}${NC}"
    else
        if ! [[ "${eulercopilot_domain}" =~ ^([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$ ]]; then
            echo -e "${RED}错误：输入的EulerCopilot域名格式不正确${NC}" >&2
            exit 1
        fi
        echo -e "${GREEN}输入域名：${eulercopilot_domain}${NC}"
    fi

    # 处理Authhub域名
    echo -e "${BLUE}请输入 Authhub 的域名配置（直接回车使用默认值 authhub.eulercopilot.local）：${NC}"
    read -p "Authhub 的前端域名: " authhub_domain
    if [[ -z "$authhub_domain" ]]; then
        authhub_domain="authhub.eulercopilot.local"
        echo -e "${GREEN}使用默认域名：${authhub_domain}${NC}"
    else
        if ! [[ "${authhub_domain}" =~ ^([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$ ]]; then
            echo -e "${RED}错误：输入的AuthHub域名格式不正确${NC}" >&2
            exit 1
        fi
        echo -e "${GREEN}输入域名：${authhub_domain}${NC}"
    fi
}

# 检查必要目录
check_directories() {
    echo -e "${BLUE}检查语义接口目录是否存在...${NC}" >&2
    if [ -d "${PLUGINS_DIR}" ]; then
        echo -e "${GREEN}目录已存在：${PLUGINS_DIR}${NC}" >&2
    else
        if mkdir -p "${PLUGINS_DIR}"; then
            echo -e "${GREEN}目录已创建：${PLUGINS_DIR}${NC}" >&2
        else
            echo -e "${RED}错误：无法创建目录 ${PLUGINS_DIR}${NC}" >&2
            exit 1
        fi
    fi
}

# 安装前检查并删除已有部署
check_and_delete_existing_deployment() {
    echo -e "${YELLOW}检查是否存在已部署的euler-copilot...${NC}" >&2
    if helm list -n euler-copilot --short | grep -q "^euler-copilot$"; then
        echo -e "${YELLOW}发现已存在的euler-copilot部署，正在删除...${NC}" >&2
        helm uninstall -n euler-copilot euler-copilot || {
            echo -e "${RED}错误：删除旧版euler-copilot失败${NC}" >&2
            exit 1
        }

        echo -e "${YELLOW}等待旧部署清理完成（10秒）...${NC}" >&2
        sleep 10
    else
        echo -e "${GREEN}未找到已存在的euler-copilot部署，继续安装...${NC}" >&2
    fi
}

# 修改YAML配置文件的方法
modify_yaml() {
    local host=$1
    echo -e "${BLUE}开始修改YAML配置文件...${NC}" >&2
    python3 "${DEPLOY_DIR}/scripts/9-other-script/modify_eulercopilot_yaml.py" \
      "${DEPLOY_DIR}/chart/euler_copilot/values.yaml" \
      "${DEPLOY_DIR}/chart/euler_copilot/values.yaml" \
      --set "models.answer.url=http://$host:11434" \
      --set "models.answer.key=sk-123456" \
      --set "models.answer.name=deepseek-llm-7b-chat" \
      --set "models.answer.ctx_length=8192" \
      --set "models.answer.max_tokens=2048" \
      --set "models.embedding.url=http://$host:11434" \
      --set "models.embedding.key=sk-123456" \
      --set "models.embedding.name=bge-m3" \
      --set "login.client.id=${client_id}" \
      --set "login.client.secret=${client_secret}" \
      --set "domain.authhub=${authhub_domain}" \
      --set "domain.euler_copilot=${eulercopilot_domain}" || {
        echo -e "${RED}错误：YAML文件修改失败${NC}" >&2
        exit 1
    }
    echo -e "${GREEN}YAML文件修改成功！${NC}" >&2
}

# 进入Chart目录的方法
enter_chart_directory() {
    echo -e "${BLUE}进入Chart目录...${NC}" >&2
    cd "${DEPLOY_DIR}/chart/" || {
        echo -e "${RED}错误：无法进入Chart目录 ${DEPLOY_DIR}/chart/${NC}" >&2
        exit 1
    }
}

# 执行Helm安装的方法
execute_helm_install() {
    local arch=$1
    echo -e "${BLUE}开始部署EulerCopilot...${NC}" >&2
    enter_chart_directory
    helm upgrade --install euler-copilot -n euler-copilot ./euler_copilot \
        --set globals.arch="$arch" || {
        echo -e "${RED}Helm 安装 EulerCopilot 失败！${NC}" >&2
        exit 1
    }
    echo -e "${GREEN}Helm安装EulerCopilot成功！${NC}" >&2
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

        # 超时处理逻辑
        if [ $elapsed -gt $timeout ]; then
            echo -e "${YELLOW}警告：部署超时！请检查以下Pod状态：${NC}" >&2
            kubectl get pods -n euler-copilot
            return 1
        fi

        # 检查所有Pod状态
        local not_running
        not_running=$(kubectl get pods -n euler-copilot -o jsonpath='{range .items[*]}{.metadata.name} {.status.phase} {.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' \
            | awk '$2 != "Running" || $3 != "True" {print $1 " " $2}')

        if [ -z "$not_running" ]; then
            echo -e "${GREEN}所有Pod已正常运行！${NC}" >&2
            kubectl get pods -n euler-copilot
            return 0
        else
            echo "等待Pod就绪（已等待 ${elapsed} 秒）..."
            echo "当前未启动Pod："
            echo "$not_running" | awk '{print "  - " $1 " (" $2 ")"}'
            sleep 10
        fi
    done
}

# 主函数执行各个步骤
main() {
    local arch host
    arch=$(get_architecture) || exit 1
    host=$(get_network_ip) || exit 1
    if ! get_client_info; then
        echo -e "${RED}获取客户端信息失败${NC}"
        exit 1
    fi
    get_user_input
    check_directories
    check_and_delete_existing_deployment
    modify_yaml "$host"
    execute_helm_install "$arch"

    # Pod状态检查并处理结果
    if check_pods_status; then
        echo -e "${GREEN}所有组件已就绪！${NC}"
    else
        echo -e "${YELLOW}注意：部分组件尚未就绪，可稍后手动检查${NC}" >&2
    fi

    # 最终部署信息输出
    echo -e "\n${GREEN}==================================================${NC}"
    echo -e "${GREEN}          EulerCopilot 部署完成！               ${NC}"
    echo -e "${GREEN}==================================================${NC}"
    echo -e "${YELLOW}EulerCopilot访问地址：\thttps://${eulercopilot_domain}${NC}"
    echo -e "${YELLOW}AuthHub管理地址：\thttps://${authhub_domain}${NC}"
    echo -e "${YELLOW}插件目录：\t\t${PLUGINS_DIR}${NC}"
    echo -e "${YELLOW}Chart目录：\t${DEPLOY_DIR}/chart/${NC}"
    echo
    echo -e "${BLUE}温馨提示："
    echo -e "${BLUE}1. 请确保域名已正确解析到集群Ingress地址${NC}"
    echo -e "${BLUE}2. 首次拉取RAG镜像可能需要约1-3分钟,Pod会稍后自动启动${NC}"
    echo -e "${BLUE}3. 查看实时状态：kubectl get pods -n euler-copilot${NC}"
    echo -e "${BLUE}4. 查看镜像：k3s crictl images${NC}"
}

# 调用主函数
main
