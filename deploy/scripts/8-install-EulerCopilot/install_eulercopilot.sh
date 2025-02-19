#!/bin/bash



# 颜色定义
RED='\e[31m'
GREEN='\e[32m'
YELLOW='\e[33m'
BLUE='\e[34m'
NC='\e[0m' # 恢复默认颜色

SCRIPTS_DIR=/home/euler-copilot-framework_openeuler/deploy/scripts/8-install-EulerCopilot
CHART_DIR=/home//euler-copilot-framework_openeuler/deploy/chart
PLUGINS_DIR="/home/eulercopilot/sematics"

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


## 获取 eth0 IP 地址
#get_eth0_ip() {
#    echo -e "${BLUE}获取网络接口 IP 地址...${NC}"
#    local timeout=20
#    local start_time=$(date +%s)
#
#    while [ $(( $(date +%s) - start_time )) -lt $timeout ]; do
#        interface=$(ip -o link show | awk '/state UP/ {print $2}' | cut -d':' -f1 | head -1)
#        [[ -n "$interface" ]] && break || sleep 1
#    done
#
#    if [[ -z "$interface" ]]; then
#        echo -e "${RED}错误：未找到可用网络接口${NC}"
#        exit 1
#    fi
#
#    host=$(ip addr show $interface | grep -w inet | awk '{print $2}' | cut -d'/' -f1)
#
#    echo -e "${GREEN}使用网络接口：${interface}，IP 地址：${host}${NC}"
#}

# 获取用户输入参数
get_user_input() {
    echo -e "${BLUE}请输入 OAuth 客户端配置：${NC}"
    read -p "Client ID: " client_id
    read -s -p "Client Secret: " client_secret
    echo

    read -p "Web前端域名: " eulercopilot_domain
    if ! [[ "${eulercopilot_domain}" =~ ^([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$ ]]; then
        echo -e "${RED}错误：输入的Copilot域名格式不正确${NC}"
        exit 1
    fi

    read -p "Authhub的前端域名: " authhub_domain
    if ! [[ "${authhub_domain}" =~ ^([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$ ]]; then
        echo -e "${RED}错误：输入的AuthHub域名格式不正确${NC}"
        exit 1
    fi

    if [[ -z "$client_id" || -z "$client_secret" || -z "$eulercopilot_domain" || -z "$authhub_domain" ]]; then
        echo -e "${RED}错误：所有输入字段都不能为空${NC}"
        exit 1
    fi
}

# 创建必要目录
create_directories() {
    echo -e "${BLUE}检查并创建数据目录...${NC}"
    if ! mkdir -p "${PLUGINS_DIR}"; then
        echo -e "${RED}错误：无法创建目录 ${PLUGINS_DIR}${NC}"
        exit 1
    fi
    echo -e "${GREEN}目录已就绪：${PLUGINS_DIR}${NC}"
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
      --set "models.embedding.url=http://$host:11434/embeddings" \
      --set "models.embedding.key=sk-123456" \
      --set "models.embedding.name=bge-m3" \
      --set "login.type=authhub" \
      --set "login.client.id=${client_id}" \
      --set "login.client.secret=${client_secret}" \
      --set "login.oidc.token_url=http://authhub-backend-service-authhub.euler-copilot.svc.cluster.local:11120/oauth2/token" \
      --set "login.oidc.user_url=http://authhub-backend-service-authhub.euler-copilot.svc.cluster.local:11120/oauth2/introspect" \
      --set "login.oidc.refresh_url=http://authhub-backend-service-authhub.euler-copilot.svc.cluster.local:11120/oauth2/refresh-token" \
      --set "login.oidc.redirect=https://${authhub_domain}/oauth2/authorize?client_id=${client_id}&redirect_uri=https://${eulercopilot_domain}/api/auth/login&scope=openid offline_access&access_type=offline&response_type=code&prompt=consent&state=235345&nonce=loser" \
      --set "domain.euler_copilot=${eulercopilot_domain}" \
      --set "domain.authhub=${authhub_domain}"

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
        
        # 修改核心检测逻辑：同时检查Phase和Ready状态
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
            echo "当前异常Pod："
            echo "$not_running" | awk '{print "  - " $1 " (" $2 ")"}'
            sleep 10
	    return 1
        fi
    done
}

# 主函数执行各个步骤
main() {
    get_eth0_ip
    get_user_input
    create_directories
    check_and_delete_existing_deployment
    modify_yaml
    enter_chart_directory
    execute_helm_install
    check_pods_status

    echo -e "\n${GREEN}==================================================${NC}"
    echo -e "${GREEN}          EulerCopilot 部署成功！               ${NC}"
    echo -e "${GREEN}==================================================${NC}"
    echo -e "${YELLOW}插件目录：${PLUGINS_DIR}${NC}"
    echo -e "${YELLOW}Chart目录位置：${CHART_DIR}${NC}"
    echo -e "${YELLOW}Copilot前端访问地址：https://${eulercopilot_domain}${NC}"
    echo -e "${YELLOW}AuthHub前端地址：https://${authhub_domain}${NC}"
}

# 调用主函数
main
