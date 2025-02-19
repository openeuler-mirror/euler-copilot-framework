#!/bin/bash

# 增强颜色定义
RESET='\033[0m'
BOLD='\033[1m'
RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
MAGENTA='\033[35m'
CYAN='\033[36m'
WHITE='\033[37m'
BG_RED='\033[41m'
BG_GREEN='\033[42m'

# 带颜色输出的进度条函数
colorful_progress() {
    local current=$1
    local total=$2
    local cols=$(tput cols)
    local progress=$((current*100/total))
    printf "${YELLOW}${BOLD}[进度]${RESET} ${BLUE}%3d%%${RESET} ${CYAN}[步骤 %d/%d]${RESET}\n" $progress $current $total
}

# 获取主脚本绝对路径并切换到所在目录
MAIN_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$MAIN_DIR" || exit 1

# 带错误检查的脚本执行函数
run_script_with_check() {
    local script_path=$1
    local script_name=$2
    local step_number=$3

    # 前置检查：脚本是否存在
    if [ ! -f "$script_path" ]; then
        echo -e "\n${RED}${BOLD}✗ 致命错误：${RESET}${YELLOW}${script_name}${RESET}${RED} 不存在 (路径: ${CYAN}${script_path}${RED})${RESET}" >&2
        exit 1
    fi

    echo -e "\n${BLUE}${BOLD}▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍"
    echo -e "${WHITE}${BOLD}▶ 步骤 ${step_number}: ${script_name}${RESET}"
    echo -e "${CYAN}🠖 执行路径：${YELLOW}${script_path}${RESET}"

    # 使用bash解释器执行并捕获输出
    if bash "$script_path" 2>&1; then
        echo -e "\n${BG_GREEN}${WHITE}${BOLD} ✓ 成功 ${RESET} ${GREEN}${script_name} 执行成功！${RESET}"
    else
        echo -e "\n${BG_RED}${WHITE}${BOLD} ✗ 失败 ${RESET} ${RED}${script_name} 执行失败！${RESET}" >&2
        exit 1
    fi
}

# 卸载所有组件
uninstall_all() {
    echo -e "\n${RED}${BOLD}⚠ 警告：此操作将永久删除所有组件和数据！${RESET}"
    read -p "$(echo -e "${YELLOW}确认要继续吗？(y/n) ${RESET}")" confirm

    if [[ $confirm != "y" && $confirm != "Y" ]]; then
        echo -e "${GREEN}取消卸载操作${RESET}"
        return
    fi

    echo -e "\n${CYAN}▸ 开始卸载所有Helm Release...${RESET}"
    local RELEASES
    RELEASES=$(helm list -n euler-copilot --short 2>/dev/null || true)

    if [ -n "$RELEASES" ]; then
        echo -e "${YELLOW}找到以下Helm Release：${RESET}"
        echo "$RELEASES" | awk '{print "  ➤ "$0}'
        for release in $RELEASES; do
            echo -e "${BLUE}正在删除: ${release}${RESET}"
            helm uninstall "$release" -n euler-copilot || echo -e "${RED}删除失败，继续执行...${RESET}"
        done
    else
        echo -e "${YELLOW}未找到需要清理的Helm Release${RESET}"
    fi

    echo -e "\n${CYAN}▸ 清理持久化存储...${RESET}"
    local pvc_list
    pvc_list=$(kubectl get pvc -n euler-copilot -o name 2>/dev/null || true)
    
    if [ -n "$pvc_list" ]; then
        echo -e "${YELLOW}找到以下PVC资源：${RESET}"
        echo "$pvc_list" | awk '{print "  ➤ "$0}'
        echo "$pvc_list" | xargs -n 1 kubectl delete -n euler-copilot || echo -e "${RED}删除失败，继续执行...${RESET}"
    else
        echo -e "${YELLOW}未找到需要清理的PVC${RESET}"
    fi

    echo -e "\n${BG_GREEN}${WHITE}${BOLD} ✓ 完成 ${RESET} ${GREEN}所有资源已清理完成${RESET}"
}

# 打印初始环境信息
echo -e "\n${MAGENTA}${BOLD}✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧"
echo -e "${WHITE}${BOLD}                   Euler Copilot 一键部署系统                   ${RESET}"
echo -e "${MAGENTA}✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧${RESET}"
echo -e "${CYAN}◈ 主工作目录：${YELLOW}${MAIN_DIR}${RESET}"

# 总步骤数和当前步骤
total_steps=8
current_step=1

# ========================================================================
# 步骤1: 环境检查
# ========================================================================
run_script_with_check "../1-check-env/check_env.sh" "环境检查" $current_step
colorful_progress $current_step $total_steps
((current_step++))

# ========================================================================
# 步骤2: 基础设施处理
# ========================================================================
echo -e "\n${BLUE}${BOLD}▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍▍"
echo -e "${WHITE}${BOLD}▶ 步骤 ${current_step}: 基础设施处理${RESET}"

if command -v k3s >/dev/null 2>&1 && command -v helm >/dev/null 2>&1; then
    echo -e "${CYAN}🠖 检测到已安装 k3s 和 helm，执行环境清理...${RESET}"
    uninstall_all
else
    echo -e "${CYAN}🠖 开始安装基础工具...${RESET}"
    run_script_with_check "../2-install-tools/install_tools.sh" "基础工具安装(k3s+helm)" $current_step
fi

colorful_progress $current_step $total_steps
((current_step++))

# ========================================================================
# 后续步骤 (3-8)
# ========================================================================
steps=(
    "../3-install-ollama/install_ollama.sh Ollama部署"
    "../4-deploy-deepseek/deploy_deepseek.sh Deepseek模型部署"
    "../5-deploy-embedding/deploy-embedding.sh Embedding服务部署"
    "../6-install-databases/install_databases.sh 数据库集群部署"
    "../7-install-authhub/install_authhub.sh Authhub部署"
    "../8-install-EulerCopilot/install_eulercopilot.sh EulerCopilot部署"
)

for step in "${steps[@]}"; do
    script_path=$(echo "$step" | awk '{print $1}')
    script_name=$(echo "$step" | awk '{sub($1 OFS, ""); print}')
    run_script_with_check "$script_path" "$script_name" $current_step
    colorful_progress $current_step $total_steps
    ((current_step++))
done

# ========================================================================
# 完成提示
# ========================================================================
echo -e "\n${BG_GREEN}${WHITE}${BOLD} ✦ 全部完成 ✦ ${RESET}"
echo -e "${GREEN}${BOLD}所有组件已成功部署！${RESET}"
echo -e "${YELLOW}请通过以下方式验证部署："
echo -e "  ➤ 检查所有Pod状态: kubectl get pods -n euler-copilot"
echo -e "  ➤ 查看服务端点: kubectl get svc -n euler-copilot"
echo -e "  ➤ 访问Web界面: http://<节点IP>:<服务端口>${RESET}"
echo -e "\n${MAGENTA}${BOLD}✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧${RESET}"
