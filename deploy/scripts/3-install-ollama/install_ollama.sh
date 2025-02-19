#!/bin/bash
set -euo pipefail

# 定义颜色代码
RED='\e[31m'
GREEN='\e[32m'
YELLOW='\e[33m'
BLUE='\e[34m'
MAGENTA='\e[35m'
CYAN='\e[36m'
RESET='\e[0m'

# 初始化全局变量
OS_ID=""

detect_os() {
    echo -e "${BLUE}步骤1/4：检测操作系统...${RESET}"
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="${ID}"
        echo -e "${GREEN}[信息] 检测到操作系统: $OS_ID${RESET}"
    else
        echo -e "${RED}[错误] 无法检测操作系统类型${RESET}" >&2
        exit 1
    fi
}

install_dependencies() {
    echo -e "${BLUE}步骤2/4：安装系统依赖...${RESET}"
    case "$OS_ID" in
        ubuntu|debian)
            if ! apt-get update && apt-get install -y curl wget tar gzip jq; then
                echo -e "${RED}[错误] APT依赖安装失败${RESET}" >&2
                exit 1
            fi
            ;;
        openEuler|centos|rhel|fedora)
            if ! yum install -y curl wget tar gzip jq; then
                echo -e "${RED}[错误] YUM依赖安装失败${RESET}" >&2
                exit 1
            fi
            ;;
        *)
            echo -e "${RED}[错误] 不支持的发行版: $OS_ID${RESET}" >&2
            exit 1
            ;;
    esac
    echo -e "${GREEN}[信息] 系统依赖安装完成${RESET}"
}

install_ollama() {
    echo -e "${BLUE}步骤3/4：安装Ollama...${RESET}"
    if command -v ollama &>/dev/null; then
        echo -e "${GREEN}[信息] Ollama已安装，跳过安装步骤${RESET}"
        return 0
    fi

    echo -e "${CYAN}[操作] 开始安装Ollama...${RESET}"
    if ! curl -o ollama_install.sh https://ollama.ai/install.sh; then
        echo -e "${RED}[错误] 下载安装脚本失败${RESET}" >&2
        exit 1
    fi

    # 替换镜像源
    if ! sed -i 's#https://github.com/#https://mirrors.tuna.tsinghua.edu.cn/github/#g' ollama_install.sh; then
        echo -e "${YELLOW}[警告] 镜像源替换失败，继续尝试安装...${RESET}"
    fi

    if ! sh ollama_install.sh; then
        echo -e "${RED}[错误] Ollama安装失败${RESET}" >&2
        echo -e "${YELLOW}排查建议："
        echo "1. 检查脚本执行权限：ls -l ollama_install.sh"
        echo "2. 查看安装日志：journalctl -u ollama -n 50${RESET}"
        exit 1
    fi
    echo -e "${GREEN}[信息] Ollama安装完成${RESET}"
}

manage_service() {
    echo -e "${BLUE}步骤4/4：配置Ollama服务...${RESET}"
    local service_file="/etc/systemd/system/ollama.service"
    
    if [ ! -f "$service_file" ]; then
        echo -e "${RED}[错误] Ollama服务文件不存在：$service_file${RESET}" >&2
        exit 1
    fi

    if ! grep -q "OLLAMA_HOST=0.0.0.0:11434" "$service_file"; then
        echo -e "${CYAN}[操作] 配置服务监听地址...${RESET}"
        if ! sed -i '/^\[Service\]/a Environment="OLLAMA_HOST=0.0.0.0:11434"' "$service_file"; then
            echo -e "${RED}[错误] 服务文件修改失败${RESET}" >&2
            exit 1
        fi
        systemctl daemon-reload
        echo -e "${GREEN}[信息] 服务配置已更新${RESET}"
    fi

    if systemctl is-active --quiet ollama; then
        echo -e "${CYAN}[操作] 重启服务应用配置...${RESET}"
        systemctl restart ollama
    else
        echo -e "${CYAN}[操作] 启动Ollama服务...${RESET}"
        systemctl enable --now ollama
    fi
    
    echo -e "${YELLOW}[状态] 等待服务初始化...${RESET}"
    sleep 10
}

### 主执行流程 ###
echo -e "${MAGENTA}=== 开始Ollama安装 ===${RESET}"
{
    detect_os
    install_dependencies
    install_ollama
    manage_service
}
echo -e "${MAGENTA}=== Ollama安装成功 ===${RESET}"
