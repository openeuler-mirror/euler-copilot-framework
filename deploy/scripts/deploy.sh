#!/bin/bash


# 顶层菜单
show_top_menu() {
    clear
    echo "=============================="
    echo "        主部署菜单             "
    echo "=============================="
    echo "0) 一键自动部署"
    echo "1) 手动分步部署"
    echo "2) 卸载所有组件并清除数据"
    echo "3) 退出程序"
    echo "=============================="
    echo -n "请输入选项编号（0-3）: "
}

# 安装选项菜单（手动部署子菜单）
show_sub_menu() {
    clear
    echo "=============================="
    echo "       手动分步部署菜单         "
    echo "=============================="
    echo "1) 执行环境检查脚本"
    echo "2) 安装k3s和helm"
    echo "3) 安装Ollama"
    echo "4) 部署Deepseek模型"
    echo "5) 部署Embedding模型"
    echo "6) 安装数据库"
    echo "7) 安装AuthHub"
    echo "8) 安装EulerCopilot"
    echo "9) 返回主菜单"
    echo "=============================="
    echo -n "请输入选项编号（0-9）: "
}

# 带错误检查的脚本执行函数
run_script_with_check() {
    local script_path=$1
    local script_name=$2

    echo "--------------------------------------------------"
    echo "开始执行：$script_name"
    "$script_path" || {
        echo -e "\n\033[31m$script_name 执行失败！\033[0m"
        exit 1
    }
    echo -e "\n\033[32m$script_name 执行成功！\033[0m"
    echo "--------------------------------------------------"
}

# 执行子菜单对应脚本
run_sub_script() {
    case $1 in
        1)
            run_script_with_check "./1-check-env/check_env.sh" "环境检查脚本"
            ;;
        2)
            run_script_with_check "./2-install-tools/install_tools.sh" "k3s和helm安装脚本"
            ;;
        3)
            run_script_with_check "./3-install-ollama/install_ollama.sh" "Ollama安装脚本"
            ;;
        4)
            run_script_with_check "./4-deploy-deepseek/deploy_deepseek.sh" "Deepseek部署脚本"
            ;;
        5)
            run_script_with_check "./5-deploy-embedding/deploy-embedding.sh" "Embedding部署脚本"
            ;;
        6)
            run_script_with_check "./6-install-databases/install_databases.sh" "数据库安装脚本"
            ;;
        7)
            run_script_with_check "./7-install-authhub/install_authhub.sh" "AuthHub安装脚本"
            ;;
        8)
            run_script_with_check "./8-install-EulerCopilot/install_eulercopilot.sh" "EulerCopilot安装脚本"
            ;;
        9)
            echo "正在返回主菜单..."
            return 2  # 特殊返回码表示返回上级菜单
            ;;
        *)
            echo -e "\033[31m无效的选项，请输入0-9之间的数字\033[0m"
            return 1
            ;;
    esac
    return 0
}

# 卸载所有组件
uninstall_all() {
    echo -e "\033[31m警告：此操作将永久删除所有组件和数据！\033[0m"
    read -p "确认要继续吗？(y/n) " confirm
    
    if [[ $confirm != "y" && $confirm != "Y" ]]; then
        echo "取消卸载操作"
        return
    fi

    echo "开始卸载所有Helm Release..."
    local RELEASES
    RELEASES=$(helm list -n euler-copilot --short || true)

    # 删除所有关联的Helm Release
    if [ -n "$RELEASES" ]; then
        echo -e "${YELLOW}找到以下Helm Release，开始清理...${NC}"
        for release in $RELEASES; do
            echo -e "${BLUE}正在删除Helm Release: ${release}${NC}"
            helm uninstall "$release" -n euler-copilot || echo -e "${RED}删除Helm Release失败，继续执行...${NC}"
        done
    else
        echo -e "${YELLOW}未找到需要清理的Helm Release${NC}"
    fi

    # 获取所有PVC列表
    local pvc_list
    pvc_list=$(kubectl get pvc -n euler-copilot -o name 2>/dev/null || true)

    # 删除PVC
    if [ -n "$pvc_list" ]; then
        echo -e "${YELLOW}找到以下PVC，开始清理...${NC}"
        echo "$pvc_list" | xargs -n 1 kubectl delete -n euler-copilot || echo -e "${RED}PVC删除失败，继续执行...${NC}"
    else
        echo -e "${YELLOW}未找到需要清理的PVC${NC}"
    fi

    echo -e "${GREEN}资源清理完成${NC}"
    echo -e "\033[32m所有组件和数据已成功清除\033[0m"
}

# 手动部署子菜单循环
manual_deployment_loop() {
    while true; do
        show_sub_menu
        read -r sub_choice
        run_sub_script "$sub_choice"
        retval=$?

        if [ $retval -eq 2 ]; then  # 返回主菜单
            break
        elif [ $retval -eq 0 ]; then
            echo "按任意键继续..."
            read -r -n 1 -s
        fi
    done
}

# 主程序循环
while true; do
    show_top_menu
    read -r main_choice
    
    case $main_choice in
        0)
            run_script_with_check "./0-one-click-deploy/one-click-deploy.sh" "一键自动部署"
            echo -e "\n\033[33m请手动登录Authhub完成后续配置："
            echo "1. 访问Authhub管理界面"
            echo "2. 创建新的应用授权"
            echo "3. 更新EulerCopilot的配置文件\033[0m"
            ;;
        1)
            manual_deployment_loop
            ;;
        2)
            uninstall_all
            echo "按任意键继续..."
            read -r -n 1 -s
            ;;
        3)
            echo "退出部署系统"
            exit 0
            ;;
        *)
            echo -e "\033[31m无效的选项，请输入0-3之间的数字\033[0m"
            sleep 1
            ;;
    esac
done
