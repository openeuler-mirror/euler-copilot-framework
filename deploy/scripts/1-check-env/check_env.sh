#!/bin/bash

# 颜色定义
COLOR_INFO='\033[34m'     # 蓝色信息
COLOR_SUCCESS='\033[32m'  # 绿色成功
COLOR_ERROR='\033[31m'    # 红色错误
COLOR_RESET='\033[0m'     # 重置颜色

function check_user {
    if [[ $(id -u) -ne 0 ]]; then
        echo -e "${COLOR_ERROR}[Error] 请以root权限运行该脚本！${COLOR_RESET}"
        return 1
    fi
    return 0
}

function check_version {
    local current_version_id="$1"
    local supported_versions=("${@:2}")  # 从第二个参数开始为支持的版本

    echo -e "${COLOR_INFO}[Info] 当前操作系统版本为：$current_version_id${COLOR_RESET}"
    for version_id in "${supported_versions[@]}"; do
        if [[ "$current_version_id" == "$version_id" ]]; then  # 精确匹配
            echo -e "${COLOR_SUCCESS}[Success] 操作系统满足兼容性要求${COLOR_RESET}"
            return 0
        fi
    done

    echo -e "${COLOR_ERROR}[Error] 操作系统不满足兼容性要求，脚本将退出${COLOR_RESET}"
    return 1
}

function check_os_version {
    local id=$(grep -E "^ID=" /etc/os-release | cut -d '"' -f 2)
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
        echo -e "${COLOR_ERROR}[Error] 当前操作系统未设置主机名，将进行主机名设置${COLOR_RESET}"
        read -p "请输入主机名：" new_hostname
        set_hostname "$new_hostname"
        return $?
    else
        echo -e "${COLOR_INFO}[Info] 当前主机名为：$current_hostname${COLOR_RESET}"
        echo -e "${COLOR_SUCCESS}[Success] 当前操作系统主机名已设置${COLOR_RESET}"
        return 0
    fi
}

function set_hostname {
    if ! command -v hostnamectl &> /dev/null; then
        echo -e "${COLOR_ERROR}[Error] hostnamectl 不存在，主机名设置可能不会持久生效${COLOR_RESET}"
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
    echo -e "${COLOR_INFO}[Info] 检查DNS服务器设置${COLOR_RESET}"
    if grep -q "^nameserver" /etc/resolv.conf; then
        echo -e "${COLOR_SUCCESS}[Success] DNS服务器已配置${COLOR_RESET}"
        return 0
    fi

    echo -e "${COLOR_ERROR}[Error] DNS服务器未配置${COLOR_RESET}"
    read -p "请输入新的DNS服务器地址：" new_dns
    set_dns "$new_dns"
    return $?
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
    local RAM_THRESHOLD=16000  # 16GB
    local current_mem=$(free -m | awk '/Mem/{print $2}')

    echo -e "${COLOR_INFO}[Info] 当前机器的RAM为：$current_mem MB${COLOR_RESET}"
    if (( current_mem < RAM_THRESHOLD )); then
        echo -e "${COLOR_ERROR}[Error] 内存容量不足 ${RAM_THRESHOLD} MB${COLOR_RESET}"
        return 1
    fi
    echo -e "${COLOR_SUCCESS}[Success] 内存容量满足要求${COLOR_RESET}"
    return 0
}

function check_disk {
    local DISK_THRESHOLD=50000  # 50GB
    local PERCENT_THRESHOLD=85  # 85%
    
    read -r available size <<< $(df -m /var/lib | awk 'NR==2{print $4,$2}')
    echo -e "${COLOR_INFO}[Info] 当前磁盘可用空间: ${available}MB, 总大小: ${size}MB${COLOR_RESET}"

    if (( available < DISK_THRESHOLD )); then
        echo -e "${COLOR_ERROR}[Error] 磁盘可用空间不足 ${DISK_THRESHOLD} MB${COLOR_RESET}"
        return 1
    fi

    local used_after=$(( size - (available - DISK_THRESHOLD) ))
    local usage_percent=$(( used_after * 100 / size ))
    
    if (( usage_percent > PERCENT_THRESHOLD )); then
        echo -e "${COLOR_ERROR}[Error] 部署后磁盘使用率将达 ${usage_percent}% (超过 ${PERCENT_THRESHOLD}%)${COLOR_RESET}"
        return 1
    fi
    
    echo -e "${COLOR_SUCCESS}[Success] 磁盘空间满足要求${COLOR_RESET}"
    return 0
}

function check_network {
    echo -e "${COLOR_INFO}[Info] 检查网络连接...${COLOR_RESET}"
    if ! command -v curl &> /dev/null; then
        echo -e "${COLOR_INFO}[Info] 正在安装curl...${COLOR_RESET}"
        yum install -y curl || { echo -e "${COLOR_ERROR}[Error] curl安装失败${COLOR_RESET}"; return 1; }
    fi

    if ! curl -IsSf --connect-timeout 5 www.baidu.com &> /dev/null; then
        echo -e "${COLOR_ERROR}[Error] 无法访问外部网络${COLOR_RESET}"
        return 1
    fi
    echo -e "${COLOR_SUCCESS}[Success] 网络连接正常${COLOR_RESET}"
    return 0
}

function check_selinux {
    local config_status=$(grep -E "^SELINUX=" /etc/selinux/config | awk -F'=' '{print $2}' | tr -d '"' | tr -d ' ')
    local runtime_status=$(getenforce 2>/dev/null)

    if [[ "$runtime_status" == "Enforcing" ]]; then
        echo -e "${COLOR_ERROR}[Error] SELinux当前处于强制模式${COLOR_RESET}"
        read -p "是否禁用SELinux？(Y/n)" choice
        case $choice in
            [nN]) 
                echo -e "${COLOR_ERROR}[Error] 已保留SELinux设置${COLOR_RESET}"
                return 1
                ;;
            *)
                sed -i 's/^SELINUX=.*/SELINUX=disabled/g' /etc/selinux/config
                setenforce 0
                echo -e "${COLOR_SUCCESS}[Success] SELinux已禁用${COLOR_RESET}"
                ;;
        esac
    elif [[ "$config_status" == "enforcing" ]]; then
        echo -e "${COLOR_ERROR}[Error] SELinux配置为强制模式（需重启生效）${COLOR_RESET}"
        return 1
    fi
    return 0
}

function check_firewall {
    if systemctl is-active --quiet firewalld; then
        echo -e "${COLOR_ERROR}[Error] FirewallD正在运行${COLOR_RESET}"
        read -p "是否关闭防火墙？(Y/n)" choice
        case $choice in
            [nN])
                echo -e "${COLOR_ERROR}[Error] 已保留防火墙设置${COLOR_RESET}"
                return 1
                ;;
            *)
                systemctl disable --now firewalld
                echo -e "${COLOR_SUCCESS}[Success] 防火墙已关闭${COLOR_RESET}"
                ;;
        esac
    else
        echo -e "${COLOR_SUCCESS}[Success] 防火墙未运行${COLOR_RESET}"
    fi
    return 0
}

function main {
    check_user || return 1
    check_os_version || return 1
    check_hostname || return 1
    check_dns || return 1
    check_ram || return 1
    check_disk || return 1
    check_network || return 1
    check_selinux || return 1
    check_firewall || return 1

    echo -e "\n${COLOR_SUCCESS}#####################################"
    echo -e "#     环境检查全部通过，可以开始部署     #"
    echo -e "#####################################${COLOR_RESET}"
    return 0
}

main
