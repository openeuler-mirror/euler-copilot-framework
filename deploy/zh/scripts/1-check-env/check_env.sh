#!/bin/bash
# 颜色定义
COLOR_INFO='\033[34m'     # 蓝色信息
COLOR_SUCCESS='\033[32m'  # 绿色成功
COLOR_ERROR='\033[31m'    # 红色错误
COLOR_WARNING='\033[33m'  # 黄色警告
COLOR_RESET='\033[0m'     # 重置颜色

# 全局模式标记
OFFLINE_MODE=false

function check_user {
    if [[ $(id -u) -ne 0 ]]; then
        echo -e "${COLOR_ERROR}[Error] 请以root权限运行该脚本！${COLOR_RESET}"
        return 1
    fi
    return 0
}

function check_version {
    local current_version_id="$1"
    local supported_versions=("${@:2}")

    echo -e "${COLOR_INFO}[Info] 当前操作系统版本为：$current_version_id${COLOR_RESET}"
    for version_id in "${supported_versions[@]}"; do
        if [[ "$current_version_id" == "$version_id" ]]; then
            echo -e "${COLOR_SUCCESS}[Success] 操作系统满足兼容性要求${COLOR_RESET}"
            return 0
        fi
    done

    echo -e "${COLOR_ERROR}[Error] 操作系统不满足兼容性要求，脚本将退出${COLOR_RESET}"
    return 1
}

function check_os_version {
    local id=$(grep '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
    local version=$(grep -E "^VERSION_ID=" /etc/os-release | cut -d '"' -f 2)

    echo -e "${COLOR_INFO}[Info] 当前发行版为：$id${COLOR_RESET}"

    case $id in
        "openEuler"|"bclinux")
            local supported_versions=("22.03" "22.09" "23.03" "23.09" "24.03")
            check_version "$version" "${supported_versions[@]}"
            ;;
        "InLinux")
            local supported_versions=("23.12")
            check_version "$version" "${supported_versions[@]}"
            ;;
        "FusionOS")
            local supported_versions=("23")
            check_version "$version" "${supported_versions[@]}"
            ;;
        "uos")
            local supported_versions=("20")
            check_version "$version" "${supported_versions[@]}"
            ;;
        "HopeOS")
            local supported_versions=("V22")
            check_version "$version" "${supported_versions[@]}"
            ;;
        "kylin")
            local supported_versions=("V10")
            check_version "$version" "${supported_versions[@]}"
            ;;
        *)
            echo -e "${COLOR_ERROR}[Error] 发行版不受支持，脚本将退出${COLOR_RESET}"
            return 1
            ;;
    esac
    return $?
}

function check_hostname {
    local current_hostname=$(cat /etc/hostname)
    if [[ -z "$current_hostname" ]]; then
        echo -e "${COLOR_ERROR}[Error] 未设置主机名，自动设置为localhost${COLOR_RESET}"
        set_hostname "localhost"
        return $?
    else
        echo -e "${COLOR_INFO}[Info] 当前主机名为：$current_hostname${COLOR_RESET}"
        echo -e "${COLOR_SUCCESS}[Success] 主机名已设置${COLOR_RESET}"
        return 0
    fi
}

function set_hostname {
    if ! command -v hostnamectl &> /dev/null; then
        echo "$1" > /etc/hostname
        echo -e "${COLOR_SUCCESS}[Success] 手动设置主机名成功${COLOR_RESET}"
        return 0
    fi

    if hostnamectl set-hostname "$1"; then
        echo -e "${COLOR_SUCCESS}[Success] 主机名设置成功${COLOR_RESET}"
        return 0
    else
        echo -e "${COLOR_ERROR}[Error] 主机名设置失败${COLOR_RESET}"
        return 1
    fi
}

function check_dns {
    echo -e "${COLOR_INFO}[Info] 检查DNS设置${COLOR_RESET}"
    if grep -q "^nameserver" /etc/resolv.conf; then
        echo -e "${COLOR_SUCCESS}[Success] DNS已配置${COLOR_RESET}"
        return 0
    fi

    if $OFFLINE_MODE; then
        echo -e "${COLOR_WARNING}[Warning] 离线模式：请手动配置内部DNS服务器${COLOR_RESET}"
        return 0
    else
        echo -e "${COLOR_ERROR}[Error] DNS未配置，自动设置为8.8.8.8${COLOR_RESET}"
        set_dns "8.8.8.8"
        return $?
    fi
}

function set_dns {
    if systemctl is-active --quiet NetworkManager; then
        local net_ic=$(nmcli -t -f NAME con show --active | head -n 1)
        if [[ -z "$net_ic" ]]; then
            echo -e "${COLOR_ERROR}[Error] 未找到活跃网络连接${COLOR_RESET}"
            return 1
        fi

        if nmcli con mod "$net_ic" ipv4.dns "$1" && nmcli con mod "$net_ic" ipv4.ignore-auto-dns yes; then
            nmcli con down "$net_ic" && nmcli con up "$net_ic"
            echo -e "${COLOR_SUCCESS}[Success] DNS设置成功${COLOR_RESET}"
            return 0
        else
            echo -e "${COLOR_ERROR}[Error] DNS设置失败${COLOR_RESET}"
            return 1
        fi
    else
        cp /etc/resolv.conf /etc/resolv.conf.bak
        echo "nameserver $1" >> /etc/resolv.conf
        echo -e "${COLOR_SUCCESS}[Success] 手动设置DNS成功${COLOR_RESET}"
        return 0
    fi
}

function check_ram {
    local RAM_THRESHOLD=16000
    local current_mem=$(free -m | awk '/Mem/{print $2}')

    echo -e "${COLOR_INFO}[Info] 当前内存：$current_mem MB${COLOR_RESET}"
    if (( current_mem < RAM_THRESHOLD )); then
        echo -e "${COLOR_ERROR}[Error] 内存不足 ${RAM_THRESHOLD} MB${COLOR_RESET}"
        return 1
    fi
    echo -e "${COLOR_SUCCESS}[Success] 内存满足要求${COLOR_RESET}"
    return 0
}

check_disk_space() {
    local DIR="$1"
    local THRESHOLD="$2"

    local USAGE=$(df --output=pcent "$DIR" | tail -n 1 | sed 's/%//g' | tr -d ' ')

    if [ "$USAGE" -ge "$THRESHOLD" ]; then
        echo -e "${COLOR_WARNING}[Warning] $DIR 的磁盘使用率已达到 ${USAGE}%，超过阈值 ${THRESHOLD}%${COLOR_RESET}"
        return 1
    else
        echo -e "${COLOR_INFO}[Info] $DIR 的磁盘使用率为 ${USAGE}%，低于阈值 ${THRESHOLD}%${COLOR_RESET}"
        return 0
    fi
}

function check_network {
    echo -e "${COLOR_INFO}[Info] 检查网络连接...${COLOR_RESET}"
    
    # 使用TCP检查代替curl
    if timeout 5 bash -c 'cat < /dev/null > /dev/tcp/www.baidu.com/80' 2>/dev/null; then
        echo -e "${COLOR_SUCCESS}[Success] 网络连接正常${COLOR_RESET}"
        return 0
    else
        echo -e "${COLOR_ERROR}[Error] 无法访问外部网络${COLOR_RESET}"
        return 1
    fi
}

function check_selinux {
    sed -i 's/^SELINUX=.*/SELINUX=disabled/g' /etc/selinux/config
    echo -e "${COLOR_SUCCESS}[Success] SELinux配置已禁用${COLOR_RESET}"
    setenforce 0 &>/dev/null
    echo -e "${COLOR_SUCCESS}[Success] SELinux已临时禁用${COLOR_RESET}"
    return 0
}

function check_firewall {
    systemctl disable --now firewalld &>/dev/null
    echo -e "${COLOR_SUCCESS}[Success] 防火墙已关闭并禁用${COLOR_RESET}"
    return 0
}

function prepare_offline {
    echo -e "${COLOR_INFO}[Info] 准备离线部署环境..."
    mkdir -p /home/eulercopilot/images
    mkdir -p /home/eulercopilot/tools
    mkdir -p /home/eulercopilot/models
    echo -e "1. 请确保已上传离线安装镜像至/home/eulercopilot/images"
    echo -e "2. 请确认本地软件仓库已配置"
    echo -e "3. 所有工具包提前下载到本地目录/home/eulercopilot/tools"
    echo -e "4. 所有模型文件提前下载到本地目录/home/eulercopilot/models${COLOR_RESET}"
}

function main {
    check_user || return 1
    check_os_version || return 1
    check_hostname || return 1
    
    # 网络检查与模式判断
    if check_network; then
        OFFLINE_MODE=false
    else
        OFFLINE_MODE=true
        echo -e "${COLOR_WARNING}[Warning] 切换到离线部署模式${COLOR_RESET}"
        prepare_offline
    fi

    check_dns || return 1
    check_ram || return 1
    check_disk_space "/" 70

    if [ $? -eq 1 ]; then
        echo -e "${COLOR_WARNING}[Warning] 需要清理磁盘空间！${COLOR_RESET}"
    else
        echo -e "${COLOR_SUCCESS}[Success] 磁盘空间正常${COLOR_RESET}"
    fi

    check_selinux || return 1
    check_firewall || return 1

    # 最终部署提示
    echo -e "\n${COLOR_SUCCESS}#####################################"
    if $OFFLINE_MODE; then
        echo -e "#   环境检查完成，准备离线部署     #"
    else
        echo -e "#   环境检查完成，准备在线部署     #"
    fi
    echo -e "#####################################${COLOR_RESET}"
    return 0
}

main
