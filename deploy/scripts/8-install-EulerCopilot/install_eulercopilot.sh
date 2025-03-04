#!/bin/bash

set -eo pipefail

# 颜色定义
RED='\e[31m'
GREEN='\e[32m'
YELLOW='\e[33m'
BLUE='\e[34m'
NC='\e[0m' # 恢复默认颜色

NAMESPACE="euler-copilot"
DEPLOY_DIR="/home/euler-copilot-framework/deploy"
PLUGINS_DIR="/home/eulercopilot/semantics"


# 获取系统架构
get_architecture() {
    local arch=$(uname -m)
    case "$arch" in
        x86_64)  arch="x86" ;;
        aarch64) arch="arm" ;;
        *)
            echo -e "${RED}错误：不支持的架构 $arch${NC}" >&2
            return 1
            ;;
    esac
    echo -e "${GREEN}检测到系统架构：${arch} (原始标识: $(uname -m))${NC}" >&2
    echo "$arch"
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

get_client_info_auto() {
    # 自动生成客户端名称（格式：client_随机8位字符）
    local client_name="client_$(openssl rand -hex 4 | cut -c1-8)"
    
    # 生成输入应答（使用随机生成的client_name）
    {
        echo "$client_name"  # 客户端名称（使用随机生成值）
        echo ""             # client_url（回车使用默认）
        echo ""             # redirect_urls（回车使用默认）
    } | python3 "${DEPLOY_DIR}/scripts/9-other-script/get_client_id_and_secret.py" > client_info.tmp 2>&1

    # 检查Python脚本执行结果
    if [ $? -ne 0 ]; then
        echo -e "${RED}错误：Python脚本执行失败${NC}"
        cat client_info.tmp
    fi

    # 提取凭证信息（保持原有逻辑）
    client_id=$(grep "client_id: " client_info.tmp | awk '{print $2}')
    client_secret=$(grep "client_secret: " client_info.tmp | awk '{print $2}')
    rm -f client_info.tmp

    # 验证结果（保持原有逻辑）
    if [ -z "$client_id" ] || [ -z "$client_secret" ]; then
        echo -e "${RED}错误：无法获取有效的客户端凭证${NC}" >&2
    fi

    # 输出结果（保持原有格式）
    echo -e "${GREEN}==============================${NC}"
    echo -e "${GREEN}Client ID:     ${client_id}${NC}"
    echo -e "${GREEN}Client Secret: ${client_secret}${NC}"
    echo -e "${GREEN}==============================${NC}"
}

get_client_info_manual() {

    # 非交互模式直接使用默认值
    if [ -t 0 ]; then  # 仅在交互式终端显示提示
        echo -e "${BLUE}请输入 Client ID: 域名（端点信息：Client ID）： ${NC}"
        read -p "> " input_id
        [ -n "$input_id" ] && client_id=$input_id

        echo -e "${BLUE}请输入 Client Secret: 域名（端点信息：Client Secret）：${NC}"
        read -p "> " input_secret
        [ -n "$input_secret" ] && client_secret=$input_secret
    fi

    # 统一验证域名格式
    echo -e "${GREEN}使用配置："
    echo "Client ID: $client_id"
    echo "Client Secret: $client_secret"

}

# # 处理域名
get_domain_input() {
    # 从环境变量读取或使用默认值
    eulercopilot_domain=${EULERCOPILOT_DOMAIN:-"www.eulercopilot.local"}
    authhub_domain=${AUTHHUB_DOMAIN:-"authhub.eulercopilot.local"}

    # 非交互模式直接使用默认值
    if [ -t 0 ]; then  # 仅在交互式终端显示提示
        echo -e "${BLUE}请输入 EulerCopilot 域名（默认：$eulercopilot_domain）：${NC}"
        read -p "> " input_euler
        [ -n "$input_euler" ] && eulercopilot_domain=$input_euler

        echo -e "${BLUE}请输入 Authhub 域名（默认：$authhub_domain）：${NC}"
        read -p "> " input_auth
        [ -n "$input_auth" ] && authhub_domain=$input_auth
    fi

    # 统一验证域名格式
    local domain_regex='^([a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,}$'
    if ! [[ $eulercopilot_domain =~ $domain_regex ]]; then
        echo -e "${RED}错误：EulerCopilot域名格式不正确${NC}" >&2
        exit 1
    fi
    if ! [[ $authhub_domain =~ $domain_regex ]]; then
        echo -e "${RED}错误：AuthHub域名格式不正确${NC}" >&2
        exit 1
    fi

    echo -e "${GREEN}使用配置："
    echo "EulerCopilot域名: $eulercopilot_domain"
    echo "Authhub域名:     $authhub_domain"
}

# 检查语义接口是否存在
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

# 检查是否存在已经部署的EulerCopilot
check_and_delete_existing_deployment() {
    echo -e "${YELLOW}检查是否存在已部署的 EulerCopilot...${NC}" >&2
    if helm list -n $NAMESPACE --short | grep -q "^$NAMESPACE$"; then
        echo -e "${YELLOW}发现已存在的 EulerCopilot 部署，正在删除...${NC}" >&2
        helm uninstall -n $NAMESPACE $NAMESPACE || {
            echo -e "${RED}错误：删除旧版 EulerCopilot 失败${NC}" >&2
            exit 1
        }

        echo -e "${YELLOW}等待旧部署清理完成（10秒）...${NC}" >&2
        sleep 10
    else
        echo -e "${GREEN}未找到已存在的 EulerCopilot 部署，继续安装...${NC}" >&2
    fi
}

# 修改配置文件
modify_yaml() {
    local host=$1
    echo -e "${BLUE}开始修改YAML配置文件...${NC}" >&2
    python3 "${DEPLOY_DIR}/scripts/9-other-script/modify_eulercopilot_yaml.py" \
      "${DEPLOY_DIR}/chart/euler_copilot/values.yaml" \
      "${DEPLOY_DIR}/chart/euler_copilot/values.yaml" \
      --set "models.answer.url=http://$host:11434" \
      --set "models.answer.key=sk-123456" \
      --set "models.answer.name=deepseek-llm-7b-chat:latest" \
      --set "models.answer.ctx_length=8192" \
      --set "models.answer.max_tokens=2048" \
      --set "models.embedding.url=http://$host:11434" \
      --set "models.embedding.key=sk-123456" \
      --set "models.embedding.name=bge-m3:latest" \
      --set "login.client.id=${client_id}" \
      --set "login.client.secret=${client_secret}" \
      --set "domain.authhub=${authhub_domain}" \
      --set "domain.euler_copilot=${eulercopilot_domain}" || {
        echo -e "${RED}错误：YAML文件修改失败${NC}" >&2
        exit 1
    }
    echo -e "${GREEN}YAML文件修改成功！${NC}" >&2
}

# 检查目录
enter_chart_directory() {
    echo -e "${BLUE}进入Chart目录...${NC}" >&2
    cd "${DEPLOY_DIR}/chart/" || {
        echo -e "${RED}错误：无法进入Chart目录 ${DEPLOY_DIR}/chart/${NC}" >&2
        exit 1
    }
}

# 执行安装
execute_helm_install() {
    local arch=$1
    echo -e "${BLUE}开始部署EulerCopilot（架构: $arch）...${NC}" >&2

    enter_chart_directory
    helm upgrade --install $NAMESPACE -n $NAMESPACE ./euler_copilot --set globals.arch=$arch --create-namespace || {
        echo -e "${RED}Helm 安装 EulerCopilot 失败！${NC}" >&2
        exit 1
    }
    echo -e "${GREEN}Helm安装 EulerCopilot 成功！${NC}" >&2
}

# 检查pod状态
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
            kubectl get pods -n $NAMESPACE -o wide
            echo -e "\n${YELLOW}建议检查：${NC}"
            echo "1. 查看未就绪Pod的日志: kubectl logs -n $NAMESPACE <pod-name>"
            echo "2. 检查PVC状态: kubectl get pvc -n $NAMESPACE"
            echo "3. 检查Service状态: kubectl get svc -n $NAMESPACE"
            return 1
        fi

        local not_running=$(kubectl get pods -n $NAMESPACE -o jsonpath='{range .items[*]}{.metadata.name} {.status.phase} {.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' \
            | awk '$2 != "Running" || $3 != "True" {print $1 " " $2}')

        if [ -z "$not_running" ]; then
            echo -e "${GREEN}所有Pod已正常运行！${NC}" >&2
            kubectl get pods -n $NAMESPACE -o wide
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
    local arch host
    arch=$(get_architecture) || exit 1
    host=$(get_network_ip) || exit 1

    if ! get_client_info_auto; then
	echo -e "${YELLOW}需要手动登录Authhub域名并创建应用，获取client信息${NC}"
        get_client_info_manual
    fi
    get_domain_input
    check_directories
    check_and_delete_existing_deployment
    modify_yaml "$host"
    execute_helm_install "$arch"

    if check_pods_status; then
        echo -e "${GREEN}所有组件已就绪！${NC}"
    else
        echo -e "${YELLOW}注意：部分组件尚未就绪，建议进行排查${NC}" >&2
    fi

    # 最终部署信息输出
    echo -e "\n${GREEN}==================================================${NC}"
    echo -e "${GREEN}          EulerCopilot 部署完成！               ${NC}"
    echo -e "${GREEN}==================================================${NC}"
    echo -e "${YELLOW}访问地址："
    echo -e "EulerCopilot UI:\thttps://${eulercopilot_domain}"
    echo -e "AuthHub 管理界面:\thttps://${authhub_domain}"
    echo -e "\n${YELLOW}系统信息："
    echo -e "业务网络IP:\t${host}"
    echo -e "系统架构:\t$(uname -m) (识别为: ${arch})"
    echo -e "插件目录:\t${PLUGINS_DIR}"
    echo -e "Chart目录:\t${DEPLOY_DIR}/chart/${NC}"
    echo -e ""
    echo -e "${BLUE}操作指南："
    echo -e "1. 查看集群状态: kubectl get all -n $NAMESPACE"
    echo -e "2. 查看实时日志: kubectl logs -n $NAMESPACE -f deployment/$NAMESPACE"
    echo -e "3. 查看POD状态：kubectl get pods -n $NAMESPACE"
    echo -e "4. 查看数据库并使用base64密码：kubectl edit secret $NAMESPACE-system -n $NAMESPACE"
    echo -e "5. 添加域名解析（示例）:"
    echo -e "   ${host} ${eulercopilot_domain}"
    echo -e "   ${host} ${authhub_domain}${NC}"
}

main

