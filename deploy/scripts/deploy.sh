#!/bin/bash

# 语言设置
LANGUAGE="zh"
COLOR_RED='\033[31m'
COLOR_GREEN='\033[32m'
COLOR_YELLOW='\033[33m'
COLOR_BLUE='\033[34m'
COLOR_NC='\033[0m'

# 语言选择函数
select_language() {
    clear
    echo "=============================="
    echo "    Language Selection / 语言选择"
    echo "=============================="
    echo "1) English (en)"
    echo "2) 中文 (zh)"
    echo "=============================="
    echo -n "请选择语言 / Please select language (1/2): "
    read -r lang_choice

    case $lang_choice in
        1) LANGUAGE="en" ;;
        2) LANGUAGE="zh" ;;
        *) 
            echo "无效选择，默认使用中文 / Invalid selection, using Chinese by default"
            LANGUAGE="zh"
            sleep 1
            ;;
    esac
}

# 获取对应语言的脚本路径
get_localized_script() {
    local base_script="$1"
    local script_dir=$(dirname "$base_script")
    local script_name=$(basename "$base_script")
    local name_without_ext="${script_name%.*}"
    local ext="${script_name##*.}"
    
    # 构建本地化脚本路径
    local localized_script="${script_dir}/${name_without_ext}_${LANGUAGE}.${ext}"
    
    # 如果本地化脚本存在，则返回本地化脚本路径，否则返回原脚本路径
    if [[ -f "$localized_script" ]]; then
        echo "$localized_script"
    else
        echo "$base_script"
    fi
}

# 文本翻译函数
t() {
    local zh_text="$1"
    local en_text="$2"
    
    if [[ "$LANGUAGE" == "zh" ]]; then
        echo "$zh_text"
    else
        echo "$en_text"
    fi
}

# 顶层菜单
show_top_menu() {
    clear
    if [[ "$LANGUAGE" == "zh" ]]; then
        echo "=============================="
        echo "        主部署菜单             "
        echo "=============================="
        echo "0) 一键自动部署"
        echo "1) 手动分步部署"
        echo "2) 重启服务"
        echo "3) 卸载所有组件并清除数据"
        echo "4) 退出程序"
        echo "=============================="
        echo -n "请输入选项编号（0-4）: "
    else
        echo "=============================="
        echo "      Main Deployment Menu     "
        echo "=============================="
        echo "0) One-click Auto Deployment"
        echo "1) Manual Step-by-step Deployment"
        echo "2) Restart Services"
        echo "3) Uninstall All Components and Clear Data"
        echo "4) Exit"
        echo "=============================="
        echo -n "Please enter option number (0-4): "
    fi
}

# 安装选项菜单（手动部署子菜单）
show_sub_menu() {
    clear
    if [[ "$LANGUAGE" == "zh" ]]; then
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
        echo -n "请输入选项编号（1-9）: "
    else
        echo "=============================="
        echo "   Manual Deployment Menu     "
        echo "=============================="
        echo "1) Execute Environment Check Script"
        echo "2) Install k3s and helm"
        echo "3) Install Ollama"
        echo "4) Deploy Deepseek Model"
        echo "5) Deploy Embedding Model"
        echo "6) Install Databases"
        echo "7) Install AuthHub"
        echo "8) Install EulerCopilot"
        echo "9) Return to Main Menu"
        echo "=============================="
        echo -n "Please enter option number (1-9): "
    fi
}

show_restart_menu() {
    clear
    if [[ "$LANGUAGE" == "zh" ]]; then
        echo "=============================="
        echo "        服务重启菜单           "
        echo "=============================="
        echo "可重启的服务列表："
        echo "1) authhub-backend"
        echo "2) authhub"
        echo "3) framework"
        echo "4) minio"
        echo "5) mongo"
        echo "6) mysql"
        echo "7) opengauss"
        echo "8) rag"
        echo "9) rag-web"
        echo "10) redis"
        echo "11) web"
        echo "12) 返回主菜单"
        echo "=============================="
        echo -n "请输入要重启的服务编号（1-12）: "
    else
        echo "=============================="
        echo "      Service Restart Menu    "
        echo "=============================="
        echo "Available services to restart:"
        echo "1) authhub-backend"
        echo "2) authhub"
        echo "3) framework"
        echo "4) minio"
        echo "5) mongo"
        echo "6) mysql"
        echo "7) opengauss"
        echo "8) rag"
        echo "9) rag-web"
        echo "10) redis"
        echo "11) web"
        echo "12) Return to Main Menu"
        echo "=============================="
        echo -n "Please enter service number to restart (1-12): "
    fi
}

# 带错误检查的脚本执行函数
run_script_with_check() {
    local script_path=$1
    local script_name=$2
    
    # 获取对应语言的脚本路径
    local localized_script=$(get_localized_script "$script_path")
    
    echo "--------------------------------------------------"
    if [[ "$LANGUAGE" == "zh" ]]; then
        echo "开始执行：$script_name"
        echo "脚本路径：$localized_script"
    else
        echo "Starting: $script_name"
        echo "Script path: $localized_script"
    fi
    
    # 检查脚本是否存在
    if [[ ! -f "$localized_script" ]]; then
        if [[ "$LANGUAGE" == "zh" ]]; then
            echo -e "\n${COLOR_RED}错误：脚本文件不存在: $localized_script${COLOR_NC}"
        else
            echo -e "\n${COLOR_RED}Error: Script file not found: $localized_script${COLOR_NC}"
        fi
        return 1
    fi
    
    # 执行脚本
    "$localized_script" || {
        if [[ "$LANGUAGE" == "zh" ]]; then
            echo -e "\n${COLOR_RED}$script_name 执行失败！${COLOR_NC}"
        else
            echo -e "\n${COLOR_RED}$script_name execution failed!${COLOR_NC}"
        fi
        return 1
    }
    
    if [[ "$LANGUAGE" == "zh" ]]; then
        echo -e "\n${COLOR_GREEN}$script_name 执行成功！${COLOR_NC}"
    else
        echo -e "\n${COLOR_GREEN}$script_name executed successfully!${COLOR_NC}"
    fi
    echo "--------------------------------------------------"
}

# 执行子菜单对应脚本
run_sub_script() {
    local base_script_path=""
    local script_description=""
    
    case $1 in
        1)
            base_script_path="./1-check-env/check_env.sh"
            script_description=$(t "环境检查脚本" "Environment Check Script")
            ;;
        2)
            base_script_path="./2-install-tools/install_tools.sh"
            script_description=$(t "k3s和helm安装脚本" "k3s and helm Installation Script")
            ;;
        3)
            base_script_path="./3-install-ollama/install_ollama.sh"
            script_description=$(t "Ollama安装脚本" "Ollama Installation Script")
            ;;
        4)
            base_script_path="./4-deploy-deepseek/deploy_deepseek.sh"
            script_description=$(t "Deepseek部署脚本" "Deepseek Deployment Script")
            ;;
        5)
            base_script_path="./5-deploy-embedding/deploy-embedding.sh"
            script_description=$(t "Embedding部署脚本" "Embedding Deployment Script")
            ;;
        6)
            base_script_path="./6-install-databases/install_databases.sh"
            script_description=$(t "数据库安装脚本" "Database Installation Script")
            ;;
        7)
            base_script_path="./7-install-authhub/install_authhub.sh"
            script_description=$(t "AuthHub安装脚本" "AuthHub Installation Script")
            ;;
        8)
            base_script_path="./8-install-EulerCopilot/install_eulercopilot.sh"
            script_description=$(t "EulerCopilot安装脚本" "EulerCopilot Installation Script")
            ;;
        9)
            if [[ "$LANGUAGE" == "zh" ]]; then
                echo "正在返回主菜单..."
            else
                echo "Returning to main menu..."
            fi
            echo "$(t "按任意键继续..." "Press any key to continue...")"
            read -r -n 1 -s
            return 2  # 特殊返回码表示返回上级菜单
            ;;
        *)
            if [[ "$LANGUAGE" == "zh" ]]; then
                echo -e "${COLOR_RED}无效的选项，请输入1-9之间的数字${COLOR_NC}"
            else
                echo -e "${COLOR_RED}Invalid option, please enter a number between 1-9${COLOR_NC}"
            fi
            return 1
            ;;
    esac
    
    run_script_with_check "$base_script_path" "$script_description"
    return $?
}

# 卸载所有组件
uninstall_all() {
    if [[ "$LANGUAGE" == "zh" ]]; then
        echo -e "${COLOR_RED}警告：此操作将永久删除所有组件和数据！${COLOR_NC}"
        read -p "确认要继续吗？(y/n) " confirm
    else
        echo -e "${COLOR_RED}Warning: This operation will permanently delete all components and data!${COLOR_NC}"
        read -p "Are you sure you want to continue? (y/n) " confirm
    fi

    if [[ $confirm != "y" && $confirm != "Y" ]]; then
        if [[ "$LANGUAGE" == "zh" ]]; then
            echo "取消卸载操作"
        else
            echo "Uninstall operation cancelled"
        fi
        return
    fi

    # 设置超时时间（单位：秒）
    local HELM_TIMEOUT=300
    local PVC_DELETE_TIMEOUT=120
    local FORCE_DELETE=false

    if [[ "$LANGUAGE" == "zh" ]]; then
        echo "开始卸载所有Helm Release..."
    else
        echo "Starting to uninstall all Helm Releases..."
    fi
    local RELEASES
    RELEASES=$(helm list -n euler-copilot --short)

    # 删除所有关联的Helm Release
    if [ -n "$RELEASES" ]; then
        if [[ "$LANGUAGE" == "zh" ]]; then
            echo -e "${COLOR_YELLOW}找到以下Helm Release，开始清理...${COLOR_NC}"
        else
            echo -e "${COLOR_YELLOW}Found the following Helm Releases, starting cleanup...${COLOR_NC}"
        fi
        for release in $RELEASES; do
            if [[ "$LANGUAGE" == "zh" ]]; then
                echo -e "${COLOR_BLUE}正在删除Helm Release: ${release}${COLOR_NC}"
            else
                echo -e "${COLOR_BLUE}Deleting Helm Release: ${release}${COLOR_NC}"
            fi
            if ! helm uninstall "$release" -n euler-copilot \
                --wait \
                --timeout ${HELM_TIMEOUT}s \
                --no-hooks; then
                if [[ "$LANGUAGE" == "zh" ]]; then
                    echo -e "${COLOR_RED}警告：Helm Release ${release} 删除异常，尝试强制删除...${COLOR_NC}"
                else
                    echo -e "${COLOR_RED}Warning: Helm Release ${release} deletion abnormal, attempting forced deletion...${COLOR_NC}"
                fi
                FORCE_DELETE=true
                helm uninstall "$release" -n euler-copilot \
                    --timeout 10s \
                    --no-hooks \
                    --force || true
            fi
        done
    else
        if [[ "$LANGUAGE" == "zh" ]]; then
            echo -e "${COLOR_YELLOW}未找到需要清理的Helm Release${COLOR_NC}"
        else
            echo -e "${COLOR_YELLOW}No Helm Releases found to clean up${COLOR_NC}"
        fi
    fi

    # 等待资源释放
    sleep 10

    # 获取所有PVC列表
    local pvc_list
    pvc_list=$(kubectl get pvc -n euler-copilot -o name 2>/dev/null)

    # 删除PVC（带重试机制）
    if [ -n "$pvc_list" ]; then
        if [[ "$LANGUAGE" == "zh" ]]; then
            echo -e "${COLOR_YELLOW}找到以下PVC，开始清理...${COLOR_NC}"
        else
            echo -e "${COLOR_YELLOW}Found the following PVCs, starting cleanup...${COLOR_NC}"
        fi
        local start_time=$(date +%s)
        local end_time=$((start_time + PVC_DELETE_TIMEOUT))

        for pvc in $pvc_list; do
            while : ; do
                # 尝试正常删除
                if kubectl delete $pvc -n euler-copilot --timeout=30s 2>/dev/null; then
                    break
                fi

                # 检查是否超时
                if [ $(date +%s) -ge $end_time ]; then
                    if [[ "$LANGUAGE" == "zh" ]]; then
                        echo -e "${COLOR_RED}错误：PVC删除超时，尝试强制清理...${COLOR_NC}"
                    else
                        echo -e "${COLOR_RED}Error: PVC deletion timeout, attempting forced cleanup...${COLOR_NC}"
                    fi

                    # 移除Finalizer强制删除
                    kubectl patch $pvc -n euler-copilot \
                        --type json \
                        --patch='[ { "op": "remove", "path": "/metadata/finalizers" } ]' 2>/dev/null || true

                    # 强制删除
                    kubectl delete $pvc -n euler-copilot \
                        --force \
                        --grace-period=0 2>/dev/null && break || true

                    # 最终确认
                    if ! kubectl get $pvc -n euler-copilot &>/dev/null; then
                        break
                    fi
                    if [[ "$LANGUAGE" == "zh" ]]; then
                        echo -e "${COLOR_RED}严重错误：无法删除PVC ${pvc}${COLOR_NC}" >&2
                    else
                        echo -e "${COLOR_RED}Critical error: Unable to delete PVC ${pvc}${COLOR_NC}" >&2
                    fi
                    return 1
                fi

                # 等待后重试
                sleep 5
                if [[ "$LANGUAGE" == "zh" ]]; then
                    echo -e "${COLOR_YELLOW}重试删除PVC: ${pvc}...${COLOR_NC}"
                else
                    echo -e "${COLOR_YELLOW}Retrying deletion of PVC: ${pvc}...${COLOR_NC}"
                fi
            done
        done
    else
        if [[ "$LANGUAGE" == "zh" ]]; then
            echo -e "${COLOR_YELLOW}未找到需要清理的PVC${COLOR_NC}"
        else
            echo -e "${COLOR_YELLOW}No PVCs found to clean up${COLOR_NC}"
        fi
    fi

    # 删除指定的 Secrets
    local secret_list=("authhub-secret" "euler-copilot-database" "euler-copilot-system")
    for secret in "${secret_list[@]}"; do
        if kubectl get secret "$secret" -n euler-copilot &>/dev/null; then
            if [[ "$LANGUAGE" == "zh" ]]; then
                echo -e "${COLOR_YELLOW}找到Secret: ${secret}，开始清理...${COLOR_NC}"
            else
                echo -e "${COLOR_YELLOW}Found Secret: ${secret}, starting cleanup...${COLOR_NC}"
            fi
            if ! kubectl delete secret "$secret" -n euler-copilot; then
                if [[ "$LANGUAGE" == "zh" ]]; then
                    echo -e "${COLOR_RED}错误：删除Secret ${secret} 失败！${COLOR_NC}" >&2
                else
                    echo -e "${COLOR_RED}Error: Failed to delete Secret ${secret}!${COLOR_NC}" >&2
                fi
                return 1
            fi
        else
            if [[ "$LANGUAGE" == "zh" ]]; then
                echo -e "${COLOR_YELLOW}未找到需要清理的Secret: ${secret}${COLOR_NC}"
            else
                echo -e "${COLOR_YELLOW}No Secret found to clean up: ${secret}${COLOR_NC}"
            fi
        fi
    done

    # 最终清理检查
    if [[ "$LANGUAGE" == "zh" ]]; then
        echo -e "${COLOR_YELLOW}执行最终资源检查...${COLOR_NC}"
    else
        echo -e "${COLOR_YELLOW}Performing final resource check...${COLOR_NC}"
    fi
    kubectl delete all --all -n euler-copilot --timeout=30s 2>/dev/null || true

    if [[ "$LANGUAGE" == "zh" ]]; then
        echo -e "${COLOR_GREEN}资源清理完成${COLOR_NC}"
        echo -e "${COLOR_GREEN}所有组件和数据已成功清除${COLOR_NC}"
    else
        echo -e "${COLOR_GREEN}Resource cleanup completed${COLOR_NC}"
        echo -e "${COLOR_GREEN}All components and data have been successfully cleared${COLOR_NC}"
    fi
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
            echo "$(t "按任意键继续..." "Press any key to continue...")"
            read -r -n 1 -s
        fi
    done
}

restart_pod() {
  local service="$1"
  if [[ -z "$service" ]]; then
    if [[ "$LANGUAGE" == "zh" ]]; then
        echo -e "${COLOR_RED}错误：请输入服务名称${COLOR_NC}"
    else
        echo -e "${COLOR_RED}Error: Please enter service name${COLOR_NC}"
    fi
    return 1
  fi

  local deployment="${service}-deploy"
  if [[ "$LANGUAGE" == "zh" ]]; then
      echo -e "${COLOR_BLUE}正在验证部署是否存在...${COLOR_NC}"
  else
      echo -e "${COLOR_BLUE}Verifying if deployment exists...${COLOR_NC}"
  fi
  if ! kubectl get deployment "$deployment" -n euler-copilot &> /dev/null; then
    if [[ "$LANGUAGE" == "zh" ]]; then
        echo -e "${COLOR_RED}错误：在 euler-copilot 命名空间中找不到部署 $deployment${COLOR_NC}"
    else
        echo -e "${COLOR_RED}Error: Deployment $deployment not found in euler-copilot namespace${COLOR_NC}"
    fi
    return 1
  fi

  if [[ "$LANGUAGE" == "zh" ]]; then
      echo -e "${COLOR_YELLOW}正在重启部署 $deployment ...${COLOR_NC}"
  else
      echo -e "${COLOR_YELLOW}Restarting deployment $deployment ...${COLOR_NC}"
  fi
  if kubectl rollout restart deployment/"$deployment" -n euler-copilot; then
    if [[ "$LANGUAGE" == "zh" ]]; then
        echo -e "${COLOR_GREEN}成功触发滚动重启！${COLOR_NC}"
        echo -e "可以使用以下命令查看状态：\nkubectl rollout status deployment/$deployment -n euler-copilot"
    else
        echo -e "${COLOR_GREEN}Successfully triggered rolling restart!${COLOR_NC}"
        echo -e "You can check the status with:\nkubectl rollout status deployment/$deployment -n euler-copilot"
    fi
    return 0
  else
    if [[ "$LANGUAGE" == "zh" ]]; then
        echo -e "${COLOR_RED}重启部署 $deployment 失败！${COLOR_NC}"
    else
        echo -e "${COLOR_RED}Failed to restart deployment $deployment!${COLOR_NC}"
    fi
    return 1
  fi
}

# 主程序
select_language

# 主程序循环改进
while true; do
    show_top_menu
    read -r main_choice

    case $main_choice in
        0)
            run_script_with_check "./0-one-click-deploy/one-click-deploy.sh" "$(t "一键自动部署" "One-click Auto Deployment")"
            echo "$(t "按任意键继续..." "Press any key to continue...")"
            read -r -n 1 -s
            ;;
        1)
            manual_deployment_loop
            ;;
        2)
            while true; do
                show_restart_menu
                read -r restart_choice
                case $restart_choice in
                    1)  service="authhub-backend" ;;
                    2)  service="authhub" ;;
                    3)  service="framework" ;;
                    4)  service="minio" ;;
                    5)  service="mongo" ;;
                    6)  service="mysql" ;;
                    7)  service="opengauss" ;;
                    8)  service="rag" ;;
                    9)  service="rag-web" ;;
                    10) service="redis" ;;
                    11) service="web" ;;
                    12) break ;;
                    *)
                        if [[ "$LANGUAGE" == "zh" ]]; then
                            echo -e "${COLOR_RED}无效的选项，请输入1-12之间的数字${COLOR_NC}"
                        else
                            echo -e "${COLOR_RED}Invalid option, please enter a number between 1-12${COLOR_NC}"
                        fi
                        continue
                        ;;
                esac

                if [[ -n "$service" ]]; then
                    restart_pod "$service"
                    echo "$(t "按任意键继续..." "Press any key to continue...")"
                    read -r -n 1 -s
                fi
            done
            ;;

        3)
            uninstall_all
            echo "$(t "按任意键继续..." "Press any key to continue...")"
            read -r -n 1 -s
            ;;
        4)
            if [[ "$LANGUAGE" == "zh" ]]; then
                echo "退出部署系统"
            else
                echo "Exiting deployment system"
            fi
            exit 0
            ;;
        *)
            if [[ "$LANGUAGE" == "zh" ]]; then
                echo -e "${COLOR_RED}无效的选项，请输入0-4之间的数字${COLOR_NC}"
            else
                echo -e "${COLOR_RED}Invalid option, please enter a number between 0-4${COLOR_NC}"
            fi
            sleep 1
            ;;
    esac
done
