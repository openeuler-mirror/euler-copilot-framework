#!/bin/bash

# Color definitions
COLOR_INFO='\033[34m'     # Blue info
COLOR_SUCCESS='\033[32m'  # Green success
COLOR_ERROR='\033[31m'    # Red error
COLOR_WARNING='\033[33m'  # Yellow warning
COLOR_RESET='\033[0m'     # Reset color

# Global mode flag
OFFLINE_MODE=false

function check_user {
    if [[ $(id -u) -ne 0 ]]; then
        echo -e "${COLOR_ERROR}[Error] Please run this script with root privileges!${COLOR_RESET}"
        return 1
    fi
    return 0
}

function check_version {
    local current_version_id="$1"
    local supported_versions=("${@:2}")

    echo -e "${COLOR_INFO}[Info] Current OS version: $current_version_id${COLOR_RESET}"
    for version_id in "${supported_versions[@]}"; do
        if [[ "$current_version_id" == "$version_id" ]]; then
            echo -e "${COLOR_SUCCESS}[Success] OS meets compatibility requirements${COLOR_RESET}"
            return 0
        fi
    done

    echo -e "${COLOR_ERROR}[Error] OS does not meet compatibility requirements, script will exit${COLOR_RESET}"
    return 1
}

function check_os_version {
    local id=$(grep '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
    local version=$(grep -E "^VERSION_ID=" /etc/os-release | cut -d '"' -f 2)

    echo -e "${COLOR_INFO}[Info] Current distribution: $id${COLOR_RESET}"

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
            echo -e "${COLOR_ERROR}[Error] Distribution not supported, script will exit${COLOR_RESET}"
            return 1
            ;;
    esac
    return $?
}

function check_hostname {
    local current_hostname=$(cat /etc/hostname)
    if [[ -z "$current_hostname" ]]; then
        echo -e "${COLOR_ERROR}[Error] Hostname not set, automatically set to localhost${COLOR_RESET}"
        set_hostname "localhost"
        return $?
    else
        echo -e "${COLOR_INFO}[Info] Current hostname: $current_hostname${COLOR_RESET}"
        echo -e "${COLOR_SUCCESS}[Success] Hostname is set${COLOR_RESET}"
        return 0
    fi
}

function set_hostname {
    if ! command -v hostnamectl &> /dev/null; then
        echo "$1" > /etc/hostname
        echo -e "${COLOR_SUCCESS}[Success] Manual hostname set successful${COLOR_RESET}"
        return 0
    fi

    if hostnamectl set-hostname "$1"; then
        echo -e "${COLOR_SUCCESS}[Success] Hostname set successfully${COLOR_RESET}"
        return 0
    else
        echo -e "${COLOR_ERROR}[Error] Hostname set failed${COLOR_RESET}"
        return 1
    fi
}

function check_dns {
    echo -e "${COLOR_INFO}[Info] Checking DNS settings${COLOR_RESET}"
    if grep -q "^nameserver" /etc/resolv.conf; then
        echo -e "${COLOR_SUCCESS}[Success] DNS configured${COLOR_RESET}"
        return 0
    fi

    if $OFFLINE_MODE; then
        echo -e "${COLOR_WARNING}[Warning] Offline mode: Please manually configure internal DNS server${COLOR_RESET}"
        return 0
    else
        echo -e "${COLOR_ERROR}[Error] DNS not configured, automatically set to 8.8.8.8${COLOR_RESET}"
        set_dns "8.8.8.8"
        return $?
    fi
}

function set_dns {
    if systemctl is-active --quiet NetworkManager; then
        local net_ic=$(nmcli -t -f NAME con show --active | head -n 1)
        if [[ -z "$net_ic" ]]; then
            echo -e "${COLOR_ERROR}[Error] No active network connection found${COLOR_RESET}"
            return 1
        fi

        if nmcli con mod "$net_ic" ipv4.dns "$1" && nmcli con mod "$net_ic" ipv4.ignore-auto-dns yes; then
            nmcli con down "$net_ic" && nmcli con up "$net_ic"
            echo -e "${COLOR_SUCCESS}[Success] DNS set successfully${COLOR_RESET}"
            return 0
        else
            echo -e "${COLOR_ERROR}[Error] DNS set failed${COLOR_RESET}"
            return 1
        fi
    else
        cp /etc/resolv.conf /etc/resolv.conf.bak
        echo "nameserver $1" >> /etc/resolv.conf
        echo -e "${COLOR_SUCCESS}[Success] Manual DNS set successful${COLOR_RESET}"
        return 0
    fi
}

function check_ram {
    local RAM_THRESHOLD=16000
    local current_mem=$(free -m | awk '/Mem/{print $2}')

    echo -e "${COLOR_INFO}[Info] Current memory: $current_mem MB${COLOR_RESET}"
    if (( current_mem < RAM_THRESHOLD )); then
        echo -e "${COLOR_ERROR}[Error] Insufficient memory ${RAM_THRESHOLD} MB${COLOR_RESET}"
        return 1
    fi
    echo -e "${COLOR_SUCCESS}[Success] Memory meets requirements${COLOR_RESET}"
    return 0
}

check_disk_space() {
    local DIR="$1"
    local THRESHOLD="$2"

    local USAGE=$(df --output=pcent "$DIR" | tail -n 1 | sed 's/%//g' | tr -d ' ')

    if [ "$USAGE" -ge "$THRESHOLD" ]; then
        echo -e "${COLOR_WARNING}[Warning] Disk usage for $DIR has reached ${USAGE}%, exceeding threshold ${THRESHOLD}%${COLOR_RESET}"
        return 1
    else
        echo -e "${COLOR_INFO}[Info] Disk usage for $DIR is ${USAGE}%, below threshold ${THRESHOLD}%${COLOR_RESET}"
        return 0
    fi
}

function check_network {
    echo -e "${COLOR_INFO}[Info] Checking network connection...${COLOR_RESET}"

    # Use TCP check instead of curl
    if timeout 5 bash -c 'cat < /dev/null > /dev/tcp/www.baidu.com/80' 2>/dev/null; then
        echo -e "${COLOR_SUCCESS}[Success] Network connection normal${COLOR_RESET}"
        return 0
    else
        echo -e "${COLOR_ERROR}[Error] Cannot access external network${COLOR_RESET}"
        return 1
    fi
}

function check_selinux {
    sed -i 's/^SELINUX=.*/SELINUX=disabled/g' /etc/selinux/config
    echo -e "${COLOR_SUCCESS}[Success] SELinux configuration disabled${COLOR_RESET}"
    setenforce 0 &>/dev/null
    echo -e "${COLOR_SUCCESS}[Success] SELinux temporarily disabled${COLOR_RESET}"
    return 0
}

function check_firewall {
    systemctl disable --now firewalld &>/dev/null
    echo -e "${COLOR_SUCCESS}[Success] Firewall closed and disabled${COLOR_RESET}"
    return 0
}

function prepare_offline {
    echo -e "${COLOR_INFO}[Info] Preparing offline deployment environment..."
    mkdir -p /home/eulercopilot/images
    mkdir -p /home/eulercopilot/tools
    mkdir -p /home/eulercopilot/models
    echo -e "1. Please ensure offline installation images are uploaded to /home/eulercopilot/images"
    echo -e "2. Please confirm local software repository is configured"
    echo -e "3. All tool packages pre-downloaded to local directory /home/eulercopilot/tools"
    echo -e "4. All model files pre-downloaded to local directory /home/eulercopilot/models${COLOR_RESET}"
}

function main {
    check_user || return 1
    check_os_version || return 1
    check_hostname || return 1

    # Network check and mode determination
    if check_network; then
        OFFLINE_MODE=false
    else
        OFFLINE_MODE=true
        echo -e "${COLOR_WARNING}[Warning] Switching to offline deployment mode${COLOR_RESET}"
        prepare_offline
    fi

    check_dns || return 1
    check_ram || return 1
    check_disk_space "/" 70

    if [ $? -eq 1 ]; then
        echo -e "${COLOR_WARNING}[Warning] Disk space cleanup required!${COLOR_RESET}"
    else
        echo -e "${COLOR_SUCCESS}[Success] Disk space normal${COLOR_RESET}"
    fi

    check_selinux || return 1
    check_firewall || return 1

    # Final deployment prompt
    echo -e "\n${COLOR_SUCCESS}#####################################"
    if $OFFLINE_MODE; then
        echo -e "#   Environment check complete, ready for offline deployment     #"
    else
        echo -e "#   Environment check complete, ready for online deployment     #"
    fi
    echo -e "#####################################${COLOR_RESET}"
    return 0
}

main
