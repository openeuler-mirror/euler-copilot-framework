#!/bin/bash

# 颜色定义
RED='\e[31m'
GREEN='\e[32m'
YELLOW='\e[33m'
BLUE='\e[34m'
NC='\e[0m' # 恢复默认颜色

# 路径变量定义
CHART_DIR="/home/euler-copilot-framework/deploy/chart"
SCRIPTS_DIR="/home/euler-copilot-framework/deploy/scripts"
DATA_DIR="/home/eulercopilot/sematics"

# 创建必要目录
create_directories() {
    echo -e "${BLUE}检查并创建数据目录...${NC}"
    if ! mkdir -p "${DATA_DIR}"; then
        echo -e "${RED}错误：无法创建目录 ${DATA_DIR}${NC}"
        exit 1
    fi
    echo -e "${GREEN}目录已就绪：${DATA_DIR}${NC}"
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
    cd 
    python ${SCRIPTS_DIR}/8-install-EulerCopilot/modify_eulercopilot_yaml.py \
      "${CHART_DIR}/euler_copilot/values.yaml" \
      "${CHART_DIR}/euler_copilot/values.yaml" \
      --set "models.answer.url=http://120.46.78.178:8000" \
      --set "models.answer.key=sk-EulerCopilot1bT1WtG2ssG92pvOPTkpT3BlbkFJVruTv8oUe" \
      --set "models.answer.name=Qwen2.5-32B-Instruct-GPTQ-Int4" \
      --set "models.answer.ctx_length=8192" \
      --set "models.answer.max_tokens=2048" \
      --set "models.embedding.url=https://192.168.50.4:8001/embedding/v1" \
      --set "models.embedding.key=sk-123456" \
      --set "models.embedding.name=bge-m3" \
      --set "login.type=oidc" \
      --set "login.client.id=623c3c2f1eca5ad5fca6c58a" \
      --set "login.client.secret=5d07c65f44fa1beb08b36f90af314aef" \
      --set "login.oidc.token_url=https://omapi.test.osinfra.cn/oneid/oidc/token" \
      --set "login.oidc.user_url=https://omapi.test.osinfra.cn/oneid/oidc/user" \
      --set "login.oidc.redirect=https://omapi.test.osinfra.cn/oneid/oidc/authorize?client_id=623c3c2f1eca5ad5fca6c58a&redirect_uri=https://qa-robot-openeuler.test.osinfra.cn/api/auth/login&scope=openid+profile+email+phone+offline_access&complementation=phone&access_type=offline&response_type=code" \
      --set "domain.euler_copilot=qa-robot-eulercopilot.test.osinfra.cn" \

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
    echo -e "${GREEN}Helm安装成功！${NC}"
}

# 检查Pod状态
check_pods_status() {
    echo -e "${BLUE}==> 等待初始化就绪（30秒）...${NC}"
    sleep 30  # 初始等待时间

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

        # 检查所有Pod状态
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



# 主函数执行各个步骤
main() {
    create_directories
    check_and_delete_existing_deployment
    modify_yaml
    enter_chart_directory
    execute_helm_install
    check_pods_status

    echo -e "\n${GREEN}==================================================${NC}"
    echo -e "${GREEN}          EulerCopilot 部署成功！               ${NC}"
    echo -e "${GREEN}==================================================${NC}"
    echo -e "${YELLOW}插件目录：${DATA_DIR}${NC}"
    echo -e "${YELLOW}Chart目录位置：${CHART_DIR}${NC}"
    echo -e "${YELLOW}前端访问地址：https://qa-robot-eulercopilot.test.osinfra.cn${NC}"
}

# 调用主函数
main
