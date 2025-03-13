#!/bin/bash

# 增强颜色定义
RESET='\033[0m'
BOLD='\033[1m'
RED='\033[38;5;196m'
GREEN='\033[38;5;46m'
YELLOW='\033[38;5;226m'
BLUE='\033[38;5;45m'
MAGENTA='\033[38;5;201m'
CYAN='\033[38;5;51m'
WHITE='\033[38;5;255m'
BG_RED='\033[48;5;196m'
BG_GREEN='\033[48;5;46m'
BG_BLUE='\033[48;5;45m'
DIM='\033[2m'

# 进度条宽度
PROGRESS_WIDTH=50
NAMESPACE="euler-copilot"
TIMEOUT=300   # 最大等待时间（秒）
INTERVAL=10   # 检查间隔（秒）


# 带颜色输出的进度条函数
colorful_progress() {
    local current=$1
    local total=$2
    local progress=$((current*100/total))
    local completed=$((PROGRESS_WIDTH*current/total))
    local remaining=$((PROGRESS_WIDTH-completed))

    printf "\r${BOLD}${BLUE}⟦${RESET}"
    printf "${BG_BLUE}${WHITE}%${completed}s${RESET}" | tr ' ' '▌'
    printf "${DIM}${BLUE}%${remaining}s${RESET}" | tr ' ' '·'
    printf "${BOLD}${BLUE}⟧${RESET} ${GREEN}%3d%%${RESET} ${CYAN}[%d/%d]${RESET}" \
        $progress $current $total
}

# 打印装饰线
print_separator() {
    echo -e "${BLUE}${BOLD}$(printf '━%.0s' $(seq 1 $(tput cols)))${RESET}"
}

# 打印步骤标题
print_step_title() {
    echo -e "\n${BG_BLUE}${WHITE}${BOLD} 步骤 $1  ${RESET} ${MAGENTA}${BOLD}$2${RESET}"
    echo -e "${DIM}${BLUE}$(printf '━%.0s' $(seq 1 $(tput cols)))${RESET}"
}

# 获取主脚本绝对路径并切换到所在目录
MAIN_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$MAIN_DIR" || exit 1

# 带错误检查的脚本执行函数（改进版）
run_script_with_check() {
    local script_path=$1
    local script_name=$2
    local step_number=$3
    local auto_input=${4:-false}

    # 前置检查：脚本是否存在
    if [ ! -f "$script_path" ]; then
        echo -e "\n${BOLD}${RED}✗ 致命错误：${RESET}${YELLOW}${script_name}${RESET}${RED} 不存在 (路径: ${CYAN}${script_path}${RED})${RESET}" >&2
        exit 1
    fi

    print_step_title $step_number "$script_name"

    # 获取绝对路径和执行目录
    local script_abs_path=$(realpath "$script_path")
    local script_dir=$(dirname "$script_abs_path")
    local script_base=$(basename "$script_abs_path")

    echo -e "${DIM}${BLUE}🠖 脚本绝对路径：${YELLOW}${script_abs_path}${RESET}"
    echo -e "${DIM}${BLUE}🠖 执行工作目录：${YELLOW}${script_dir}${RESET}"
    echo -e "${DIM}${BLUE}🠖 开始执行时间：${YELLOW}$(date +'%Y-%m-%d %H:%M:%S')${RESET}"

    # 创建临时日志文件
    local log_file=$(mktemp)
    echo -e "${DIM}${BLUE}🠖 临时日志文件：${YELLOW}${log_file}${RESET}"

    # 执行脚本（带自动输入处理和实时日志输出）
    local exit_code=0
    if $auto_input; then
        (cd "$script_dir" && yes "" | bash "$script_base" 2>&1 | tee "$log_file")
    else
        (cd "$script_dir" && bash "$script_base" 2>&1 | tee "$log_file")
    fi
    exit_code=${PIPESTATUS[0]}

    # 处理执行结果
    if [ $exit_code -eq 0 ]; then
        echo -e "\n${BOLD}${GREEN}✓ ${script_name} 执行成功！${RESET}"
        echo -e "${DIM}${CYAN}$(printf '%.0s─' $(seq 1 $(tput cols)))${RESET}"
        echo -e "${DIM}${CYAN}操作日志：${RESET}"
        cat "$log_file" | sed -e "s/^/${DIM}${CYAN}  🠖 ${RESET}/"
        echo -e "${DIM}${CYAN}$(printf '%.0s─' $(seq 1 $(tput cols)))${RESET}"
    else
        echo -e "\n${BOLD}${RED}✗ ${script_name} 执行失败！${RESET}" >&2
        echo -e "${DIM}${RED}$(printf '%.0s─' $(seq 1 $(tput cols)))${RESET}" >&2
        echo -e "${DIM}${RED}错误日志：${RESET}" >&2
        cat "$log_file" | sed -e "s/^/${DIM}${RED}  ✗ ${RESET}/" >&2
        echo -e "${DIM}${RED}$(printf '%.0s─' $(seq 1 $(tput cols)))${RESET}" >&2
        rm "$log_file"
        exit 1
    fi

    rm "$log_file"
    return $exit_code
}

# 卸载所有组件
uninstall_all() {
    echo -e "\n${CYAN}▸ 开始卸载所有Helm Release...${RESET}"
    local RELEASES
    RELEASES=$(helm list -n $NAMESPACE --short 2>/dev/null || true)

    if [ -n "$RELEASES" ]; then
        echo -e "${YELLOW}找到以下Helm Release：${RESET}"
        echo "$RELEASES" | awk '{print "  ➤ "$0}'
        for release in $RELEASES; do
            echo -e "${BLUE}正在删除: ${release}${RESET}"
            helm uninstall "$release" -n $NAMESPACE || echo -e "${RED}删除失败，继续执行...${RESET}"
        done
    else
        echo -e "${YELLOW}未找到需要清理的Helm Release${RESET}"
    fi

    echo -e "\n${CYAN}▸ 清理持久化存储...${RESET}"
    local pvc_list
    pvc_list=$(kubectl get pvc -n $NAMESPACE -o name 2>/dev/null || true)

    if [ -n "$pvc_list" ]; then
        echo -e "${YELLOW}找到以下PVC资源：${RESET}"
        echo "$pvc_list" | awk '{print "  ➤ "$0}'
        echo "$pvc_list" | xargs -n 1 kubectl delete -n $NAMESPACE || echo -e "${RED}删除失败，继续执行...${RESET}"
    else
        echo -e "${YELLOW}未找到需要清理的PVC${RESET}"
    fi

    echo -e "\n${CYAN}▸ 清理Secret资源...${RESET}"
    local secret_list
    secret_list=$(kubectl get secret -n $NAMESPACE -o name 2>/dev/null || true)

    if [ -n "$secret_list" ]; then
        echo -e "${YELLOW}找到以下Secret资源：${RESET}"
        echo "$secret_list" | awk '{print "  ➤ "$0}'
        echo "$secret_list" | xargs -n 1 kubectl delete -n $NAMESPACE || echo -e "${RED}删除失败，继续执行...${RESET}"
    else
        echo -e "${YELLOW}未找到需要清理的Secret${RESET}"
    fi

    echo -e "\n${BG_GREEN}${WHITE}${BOLD} ✓ 完成 ${RESET} ${GREEN}所有资源已清理完成${RESET}"
}

# 主界面显示
show_header() {
    clear
    echo -e "\n${BOLD}${MAGENTA}$(printf '✧%.0s' $(seq 1 $(tput cols)))${RESET}"
    echo -e "${BOLD}${WHITE}                  Euler Copilot 一键部署系统                  ${RESET}"
    echo -e "${BOLD}${MAGENTA}$(printf '✧%.0s' $(seq 1 $(tput cols)))${RESET}"
    echo -e "${CYAN}◈ 主工作目录：${YELLOW}${MAIN_DIR}${RESET}\n"
}

# 初始化部署流程
start_deployment() {
    local total_steps=8
    local current_step=1

    # 步骤配置（脚本路径 脚本名称 自动输入）
    local steps=(
        "../1-check-env/check_env.sh 环境检查 false"
        "_conditional_tools_step 基础工具安装(k3s+helm) true"
        "../3-install-ollama/install_ollama.sh Ollama部署 true"
        "../4-deploy-deepseek/deploy_deepseek.sh Deepseek模型部署 false"
        "../5-deploy-embedding/deploy-embedding.sh Embedding服务部署 false"
        "../6-install-databases/install_databases.sh 数据库集群部署 false"
        "../7-install-authhub/install_authhub.sh Authhub部署 true"
	"_conditional_eulercopilot_step EulerCopilot部署 true"
    )

    for step in "${steps[@]}"; do
        local script_path=$(echo "$step" | awk '{print $1}')
        local script_name=$(echo "$step" | awk '{sub($1 OFS, ""); print $1}')
        local auto_input=$(echo "$step" | awk '{print $NF}')
	if [[ "$script_path" == "_conditional_tools_step" ]]; then
            handle_tools_step $current_step
        elif [[ "$script_path" == "_conditional_eulercopilot_step" ]]; then
            handle_eulercopilot_step $current_step
	    sleep 60
        elif ! run_script_with_check "$script_path" "$script_name" $current_step $auto_input; then
            echo "Error: Script execution failed"
        fi

        colorful_progress $current_step $total_steps
        ((current_step++))
    done

}

# 处理工具安装步骤
handle_tools_step() {
    local current_step=$1
    if command -v k3s >/dev/null 2>&1 && command -v helm >/dev/null 2>&1; then
        echo -e "${CYAN}🠖 检测到已安装 k3s 和 helm，执行环境清理...${RESET}"
        uninstall_all
    else
        run_script_with_check "../2-install-tools/install_tools.sh" "基础工具安装" $current_step true
    fi
}

# 处理工具安装步骤
handle_eulercopilot_step() {
    local current_step=$1
    sleep 60
    run_script_with_check "../8-install-EulerCopilot/install_eulercopilot.sh" "EulerCopilot部署" $current_step true
    
}

# 主执行流程
show_header
start_deployment
