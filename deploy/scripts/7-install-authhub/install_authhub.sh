#!/bin/bash


set -eo pipefail

RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
NC='\033[0m'

DEPLOY_DIR="/home/euler-copilot-framework/deploy"


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

    local pvc_list
    pvc_list=$(kubectl get pvc -n euler-copilot -o name | grep 'persistentvolumeclaim/mysql-pvc' 2>/dev/null || true)

    if [ -n "$pvc_list" ]; then
        echo -e "${YELLOW}找到以下PVC，开始清理...${NC}"
        echo "$pvc_list" | xargs -n 1 kubectl delete -n euler-copilot || echo -e "${RED}PVC删除失败，继续执行...${NC}"
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

modify_yaml() {
    echo -e "${BLUE}开始修改YAML配置文件...${NC}"
    python3 "${DEPLOY_DIR}/scripts/9-other-script/modify_eulercopilot_yaml.py" \
      "${DEPLOY_DIR}/chart/authhub/values.yaml" \
      "${DEPLOY_DIR}/chart/authhub/values.yaml" \
      --set "domain.authhub=${authhub_domain}"

    if [ $? -ne 0 ]; then
        echo -e "${RED}错误：YAML文件修改失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}YAML文件修改成功！${NC}"
}

helm_install() {
    echo -e "${BLUE}==> 进入部署目录...${NC}"
    [ ! -d "${DEPLOY_DIR}/chart" ] && {
        echo -e "${RED}错误：部署目录不存在 ${DEPLOY_DIR}/chart ${NC}"
        return 1
    }
    cd "${DEPLOY_DIR}/chart"

    echo -e "${BLUE}正在安装 authhub...${NC}"
    helm install authhub -n euler-copilot ./authhub || {
        echo -e "${RED}Helm 安装 authhub 失败！${NC}"
        return 1
    }
}

check_pods_status() {
    echo -e "${BLUE}==> 等待初始化就绪（30秒）...${NC}"
    sleep 30

    local timeout=300
    local start_time=$(date +%s)

    echo -e "${BLUE}开始监控Authhub Pod状态（总超时时间300秒）...${NC}"

    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [ $elapsed -gt $timeout ]; then
            echo -e "${RED}错误：部署超时！${NC}"
            kubectl get pods -n euler-copilot --selector=app.kubernetes.io/instance=authhub
            return 1
        fi

        # 检查所有属于authhub的Pod状态
        local not_running=$(kubectl get pods -n euler-copilot --selector=app.kubernetes.io/instance=authhub -o jsonpath='{range .items[*]}{.metadata.name} {.status.phase}{"\n"}{end}' | grep -v "Running")

        if [ -z "$not_running" ]; then
            echo -e "${GREEN}所有Authhub Pod已正常运行！${NC}"
            kubectl get pods -n euler-copilot --selector=app.kubernetes.io/instance=authhub
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
    get_user_input
    modify_yaml
    helm_install
    check_pods_status

    echo -e "\n${GREEN}========================="
    echo "Authhub 部署完成！"
    echo -e "Authhub登录地址为: https://${authhub_domain}"
    echo -e "默认账号密码: administrator/changeme"
    echo -e "=========================${NC}"
}

trap 'echo -e "${RED}操作被中断！${NC}"; exit 1' INT
main "$@"
