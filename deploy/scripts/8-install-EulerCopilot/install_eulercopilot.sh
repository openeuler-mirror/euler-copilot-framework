#!/bin/bash


set -eo pipefail

# 颜色定义
RED='\e[31m'
GREEN='\e[32m'
YELLOW='\e[33m'
BLUE='\e[34m'
NC='\e[0m' # 恢复默认颜色

SCRIPTS_DIR=/home/euler-copilot-framework/deploy/scripts/8-install-EulerCopilot
CHART_DIR=/home/euler-copilot-framework/deploy/chart
PLUGINS_DIR="/home/eulercopilot/semantics"

get_eth0_ip() {
    echo -e "${BLUE}获取 eth0 网络接口 IP 地址...${NC}"
    local timeout=20
    local start_time=$(date +%s)
    local interface="eth0"

    # 检查 eth0 是否存在，并等待其变为可用状态
    while [ $(( $(date +%s) - start_time )) -lt $timeout ]; do
        if ip link show "$interface" > /dev/null 2>&1; then
            break
        else
            sleep 1
        fi
    done

    if ! ip link show "$interface" > /dev/null 2>&1; then
        echo -e "${RED}错误：未找到网络接口 ${interface}${NC}"
        exit 1
    fi

    # 获取 IP 地址
    host=$(ip addr show "$interface" | grep -w inet | awk '{print $2}' | cut -d'/' -f1)

    if [[ -z "$host" ]]; then
        echo -e "${RED}错误：未能从接口 ${interface} 获取 IP 地址${NC}"
        exit 1
    fi

    echo -e "${GREEN}使用网络接口：${interface}，IP 地址：${host}${NC}"
}

get_user_input() {
    echo -e "${BLUE}请输入 OAuth 客户端配置：${NC}"
    read -p "Client ID: " client_id
    read -s -p "Client Secret: " client_secret

    echo

    # 检查必填字段
    if [[ -z "$client_id" || -z "$client_secret" ]]; then
        echo -e "${RED}错误：Client Secret 存在空行，请重新输入${NC}"
        read -s -p "Client Secret: " client_secret
        echo
        echo -e "${GREEN}Client Secret 已正确输入${NC}"
    fi

    # 处理Copilot域名
    echo -e "${BLUE}请输入 EulerCopilot 域名（直接回车使用默认值 www.eulercopilot.local）：${NC}"
    read -p "EulerCopilot 的前端域名: " eulercopilot_domain

    if [[ -z "$eulercopilot_domain" ]]; then
        eulercopilot_domain="www.eulercopilot.local"
        echo -e "${GREEN}使用默认域名：${eulercopilot_domain}${NC}"
    else
        if ! [[ "${eulercopilot_domain}" =~ ^([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$ ]]; then
            echo -e "${RED}错误：输入的EulerCopilot域名格式不正确${NC}"
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
            echo -e "${RED}错误：输入的AuthHub域名格式不正确${NC}"
            exit 1
        fi
        echo -e "${GREEN}输入域名：${authhub_domain}${NC}"
    fi

}

# 检查必要目录
check_directories() {
    echo -e "${BLUE}检查语义接口目录是否存在...${NC}"
    if [ -d "${PLUGINS_DIR}" ]; then
        echo -e "${GREEN}目录已存在：${PLUGINS_DIR}${NC}"
    else
        if mkdir -p "${PLUGINS_DIR}"; then
            echo -e "${GREEN}目录已创建：${PLUGINS_DIR}${NC}"
        else
            echo -e "${RED}错误：无法创建目录 ${PLUGINS_DIR}${NC}"
            exit 1
        fi
    fi
}

# 安装前检查并删除已有部署
check_and_delete_existing_deployment() {
    echo -e "${YELLOW}检查是否存在已部署的euler-copilot...${NC}"
    if helm list -n euler-copilot --short | grep -q "^euler-copilot$"; then
        echo -e "${YELLOW}发现已存在的euler-copilot部署，正在删除...${NC}"
        helm uninstall -n euler-copilot euler-copilot

        if [ $? -ne 0 ]; then
            echo -e "${RED}错误：删除旧版euler-copilot失败${NC}"
            exit 1
        fi

        echo -e "${YELLOW}等待旧部署清理完成（10秒）...${NC}"
        sleep 10
    else
        echo -e "${GREEN}未找到已存在的euler-copilot部署，继续安装...${NC}"
    fi
}

# 修改YAML配置文件的方法
modify_yaml() {
    echo -e "${BLUE}开始修改YAML配置文件...${NC}"
    python "${SCRIPTS_DIR}/modify_eulercopilot_yaml.py" \
      "${CHART_DIR}/euler_copilot/values.yaml" \
      "${CHART_DIR}/euler_copilot/values.yaml" \
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
      --set "domain.euler_copilot=${eulercopilot_domain}"

    if [ $? -ne 0 ]; then
        echo -e "${RED}错误：YAML文件修改失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}YAML文件修改成功！${NC}"
}

# 进入Chart目录的方法
enter_chart_directory() {
    echo -e "${BLUE}进入Chart目录...${NC}"
    cd "${CHART_DIR}" || {
        echo -e "${RED}错误：无法进入Chart目录 ${CHART_DIR}${NC}"
        exit 1
    }
}

# 执行Helm安装的方法
execute_helm_install() {
    echo -e "${BLUE}开始部署EulerCopilot...${NC}"
    helm install -n euler-copilot euler-copilot ./euler_copilot

    if [ $? -ne 0 ]; then
        echo -e "${RED}错误：Helm安装失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}Helm安装EulerCopilot成功！${NC}"
}

check_pods_status() {
    echo -e "${BLUE}==> 等待初始化就绪（30秒）...${NC}"
    sleep 30

    local timeout=100
    local start_time=$(date +%s)

    echo -e "${BLUE}开始监控Pod状态（总超时时间300秒）...${NC}"
    echo -e "${BLUE}镜像拉取中...${NC}"

    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        # 超时处理逻辑
        if [ $elapsed -gt $timeout ]; then
            echo -e "${YELLOW}警告：部署超时！请检查以下Pod状态：${NC}"
            kubectl get pods -n euler-copilot
            echo -e "${YELLOW}注意：部分Pod可能仍在启动中，可稍后手动检查${NC}"
            return 1
        fi

        # 检查所有Pod状态
        local not_running=$(
            kubectl get pods -n euler-copilot -o jsonpath='{range .items[*]}{.metadata.name} {.status.phase} {.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' \
            | awk '$2 != "Running" || $3 != "True" {print $1 " " $2}'
        )

        if [ -z "$not_running" ]; then
            echo -e "${GREEN}所有Pod已正常运行！${NC}"
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
    get_eth0_ip
    get_user_input
    check_directories
    check_and_delete_existing_deployment
    modify_yaml
    enter_chart_directory
    execute_helm_install

    # Pod状态检查并处理结果
    if check_pods_status; then
        echo -e "${GREEN}所有组件已就绪！${NC}"
    else
        echo -e "${YELLOW}注意：部分组件尚未就绪，可稍后手动检查${NC}"
    fi

    # 最终部署信息输出
    echo -e "\n${GREEN}==================================================${NC}"
    echo -e "${GREEN}          EulerCopilot 部署完成！               ${NC}"
    echo -e "${GREEN}==================================================${NC}"
    echo -e "${YELLOW}EulerCopilot访问地址：\thttps://${eulercopilot_domain}${NC}"
    echo -e "${YELLOW}AuthHub管理地址：\thttps://${authhub_domain}${NC}"
    echo -e "${YELLOW}插件目录：\t\t${PLUGINS_DIR}${NC}"
    echo -e "${YELLOW}Chart目录：\t${CHART_DIR}${NC}"
    echo
    echo -e "${BLUE}温馨提示："
    echo -e "${BLUE}1. 请确保域名已正确解析到集群Ingress地址${NC}"
    echo -e "${BLUE}2. 首次拉取RAG镜像可能需要约1-3分钟,POD会稍后自动启动${NC}"
    echo -e "${BLUE}3. 查看实时状态：kubectl get pods -n euler-copilot${NC}"
    echo -e "${BLUE}4. 查看镜像：k3s crictl images${NC}"
}

# 调用主函数
main
