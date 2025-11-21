#!/bin/bash

set -eo pipefail

# 颜色定义
RED='\e[31m'
GREEN='\e[32m'
YELLOW='\e[33m'
BLUE='\e[34m'
NC='\e[0m' # 恢复默认颜色

NAMESPACE="euler-copilot"
PLUGINS_DIR="/var/lib/eulercopilot"

# 全局变量声明
client_id=""
client_secret=""
eulercopilot_address=""
auth_service_type=""
auth_service_address=""
auth_policy=""  # 新增：检测到的认证策略
use_tls=""
tls_cert_path=""
tls_key_path=""

SCRIPT_PATH="$(
  cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1
  pwd
)/$(basename "${BASH_SOURCE[0]}")"

DEPLOY_DIR="$(
  canonical_path=$(readlink -f "$SCRIPT_PATH" 2>/dev/null || echo "$SCRIPT_PATH")
  dirname "$(dirname "$(dirname "$canonical_path")")"
)"

# 显示帮助信息
show_help() {
    echo -e "${GREEN}用法: $0 [选项]"
    echo -e "选项:"
    echo -e "  --help                   显示此帮助信息"
    echo -e "  --eulercopilot_address   指定EulerCopilot前端访问URL"
    echo -e "  --authhub_address        指定AuthHub认证服务地址"
    echo -e "  --authelia_address       指定Authelia认证服务地址"
    echo -e "  --enable-tls             启用TLS证书支持"
    echo -e "  --tls-cert               指定TLS证书文件路径"
    echo -e "  --tls-key                指定TLS私钥文件路径"
    echo -e "  --generate-cert          为指定域名生成自签名证书"
    echo -e ""
    echo -e "示例:"
    echo -e "  $0 --eulercopilot_address http://myhost:30080"
    echo -e "  $0 --eulercopilot_address http://myhost:30080 --authhub_address http://139.9.242.191:30081"
    echo -e "  $0 --eulercopilot_address https://myhost:30443 --enable-tls --generate-cert myhost"
    echo -e "  $0 --eulercopilot_address https://myhost:30443 --enable-tls --tls-cert /path/to/cert.crt --tls-key /path/to/key.key${NC}"
    echo -e ""
    echo -e "${YELLOW}注意: 鉴权服务将自动检测并提供选择${NC}"
    exit 0
}

# 解析命令行参数
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help)
                show_help
                ;;
            --eulercopilot_address)
                if [ -n "$2" ]; then
                    eulercopilot_address="$2"
                    shift
                else
                    echo -e "${RED}错误: --eulercopilot_address 需要提供一个值${NC}" >&2
                    exit 1
                fi
                ;;
            --authhub_address)
                if [ -n "$2" ]; then
                    auth_service_address="$2"
                    auth_service_type="authhub"
                    shift
                else
                    echo -e "${RED}错误: --authhub_address 需要提供一个值${NC}" >&2
                    exit 1
                fi
                ;;
            --authelia_address)
                if [ -n "$2" ]; then
                    auth_service_address="$2"
                    auth_service_type="authelia"
                    shift
                else
                    echo -e "${RED}错误: --authelia_address 需要提供一个值${NC}" >&2
                    exit 1
                fi
                ;;
            --enable-tls)
                use_tls="true"
                ;;
            --tls-cert)
                if [ -n "$2" ]; then
                    tls_cert_path="$2"
                    shift
                else
                    echo -e "${RED}错误: --tls-cert 需要提供证书文件路径${NC}" >&2
                    exit 1
                fi
                ;;
            --tls-key)
                if [ -n "$2" ]; then
                    tls_key_path="$2"
                    shift
                else
                    echo -e "${RED}错误: --tls-key 需要提供私钥文件路径${NC}" >&2
                    exit 1
                fi
                ;;
            --generate-cert)
                if [ -n "$2" ]; then
                    generate_cert_domain="$2"
                    use_tls="true"
                    shift
                else
                    echo -e "${RED}错误: --generate-cert 需要提供域名${NC}" >&2
                    exit 1
                fi
                ;;
            *)
                echo -e "${RED}未知选项: $1${NC}" >&2
                show_help
                exit 1
                ;;
        esac
        shift
    done
}

# TLS证书管理函数
manage_tls_certificates() {
    local tls_cert_manager="${DEPLOY_DIR}/scripts/9-other-script/tls_cert_manager.sh"
    
    # 检查TLS证书管理工具是否存在
    if [ ! -f "$tls_cert_manager" ]; then
        echo -e "${RED}错误: TLS证书管理工具不存在: $tls_cert_manager${NC}" >&2
        exit 1
    fi
    
    # 如果需要生成证书
    if [ -n "$generate_cert_domain" ]; then
        echo -e "${BLUE}为域名 '$generate_cert_domain' 生成自签名证书...${NC}"
        if ! "$tls_cert_manager" --generate "$generate_cert_domain"; then
            echo -e "${RED}错误: 生成自签名证书失败${NC}" >&2
            exit 1
        fi
        
        # 设置证书路径
        local cert_name="${generate_cert_domain//[^a-zA-Z0-9]/_}"
        local cert_dir="${DEPLOY_DIR}/scripts/9-other-script/certs/${cert_name}"
        tls_cert_path="$cert_dir/tls.crt"
        tls_key_path="$cert_dir/tls.key"
        
        echo -e "${GREEN}自签名证书生成完成${NC}"
        echo -e "证书路径: $tls_cert_path"
        echo -e "私钥路径: $tls_key_path"
    fi
    
    # 验证证书文件
    if [ "$use_tls" = "true" ]; then
        if [ -z "$tls_cert_path" ] || [ -z "$tls_key_path" ]; then
            echo -e "${RED}错误: 启用TLS但未提供证书文件路径${NC}" >&2
            echo -e "${YELLOW}请使用 --tls-cert 和 --tls-key 指定证书文件，或使用 --generate-cert 生成自签名证书${NC}" >&2
            exit 1
        fi
        
        if [ ! -f "$tls_cert_path" ]; then
            echo -e "${RED}错误: 证书文件不存在: $tls_cert_path${NC}" >&2
            exit 1
        fi
        
        if [ ! -f "$tls_key_path" ]; then
            echo -e "${RED}错误: 私钥文件不存在: $tls_key_path${NC}" >&2
            exit 1
        fi
        
        # 验证证书
        echo -e "${BLUE}验证TLS证书...${NC}"
        if ! "$tls_cert_manager" --verify "$tls_cert_path"; then
            echo -e "${RED}错误: 证书验证失败${NC}" >&2
            exit 1
        fi
        
        echo -e "${GREEN}TLS证书验证通过${NC}"
    fi
}

# 检查authelia服务的HTTPS协议和TLS证书
check_authelia_https_requirements() {
    if [ "$auth_service_type" = "authelia" ]; then
        echo -e "${BLUE}检查authelia鉴权服务的HTTPS要求...${NC}"
        
        # 检查鉴权服务地址是否使用HTTPS协议
        if [[ ! "$auth_service_address" =~ ^https:// ]]; then
            echo -e "${RED}错误: authelia鉴权服务必须使用HTTPS协议${NC}" >&2
            echo -e "${YELLOW}当前地址: $auth_service_address${NC}" >&2
            echo -e "${YELLOW}请确保authelia服务配置为HTTPS访问${NC}" >&2
            exit 1
        fi
        
        # 强制要求TLS证书
        if [ "$use_tls" != "true" ]; then
            echo -e "${YELLOW}警告: 检测到authelia鉴权服务，强制启用TLS证书支持${NC}"
            use_tls="true"
            
            # 如果没有提供证书，提示用户选择
            if [ -z "$tls_cert_path" ] && [ -z "$generate_cert_domain" ]; then
                echo -e "${BLUE}authelia鉴权服务需要TLS证书，请选择：${NC}"
                echo -e "1) 生成自签名证书"
                echo -e "2) 使用已有证书"
                
                if [ -t 0 ]; then  # 交互式模式
                    while true; do
                        read -p "请选择 (1/2): " choice
                        case "$choice" in
                            1)
                                # 从鉴权服务地址提取域名
                                local domain=$(echo "$auth_service_address" | sed -E 's|https?://([^:/]+).*|\1|')
                                generate_cert_domain="$domain"
                                echo -e "${GREEN}将为域名 '$domain' 生成自签名证书${NC}"
                                break
                                ;;
                            2)
                                echo -e "${YELLOW}请重新运行脚本并使用 --tls-cert 和 --tls-key 参数指定证书文件${NC}"
                                exit 1
                                ;;
                            *)
                                echo -e "${RED}无效选择，请输入1或2${NC}"
                                ;;
                        esac
                    done
                else
                    # 非交互式模式，自动生成证书
                    local domain=$(echo "$auth_service_address" | sed -E 's|https?://([^:/]+).*|\1|')
                    generate_cert_domain="$domain"
                    echo -e "${GREEN}非交互式模式：将为域名 '$domain' 自动生成自签名证书${NC}"
                fi
            fi
        fi
        
        echo -e "${GREEN}authelia HTTPS要求检查通过${NC}"
    fi
}

# 创建TLS Secret
create_tls_secret() {
    if [ "$use_tls" = "true" ] && [ -n "$tls_cert_path" ] && [ -n "$tls_key_path" ]; then
        echo -e "${BLUE}创建TLS Secret...${NC}"
        
        local secret_name="eulercopilot-tls-secret"
        
        # 删除现有Secret（如果存在）
        kubectl delete secret "$secret_name" -n "$NAMESPACE" 2>/dev/null || true
        
        # 创建TLS Secret
        if kubectl create secret tls "$secret_name" \
            --cert="$tls_cert_path" \
            --key="$tls_key_path" \
            -n "$NAMESPACE"; then
            echo -e "${GREEN}TLS Secret创建成功: $secret_name${NC}"
        else
            echo -e "${RED}错误: TLS Secret创建失败${NC}" >&2
            exit 1
        fi
    fi
}

# 安装成功信息显示函数
show_success_message() {
    local host=$1
    local arch=$2 

    echo -e "\n${GREEN}==================================================${NC}"
    echo -e "${GREEN}          EulerCopilot 部署完成！                 ${NC}"
    echo -e "${GREEN}==================================================${NC}"

    echo -e "${YELLOW}访问信息：${NC}"
    echo -e "EulerCopilot UI:    ${eulercopilot_address}"
    if [ -n "$auth_service_address" ]; then
        echo -e "鉴权服务 (${auth_service_type}): ${auth_service_address}"
    fi
    if [ "$use_tls" = "true" ]; then
        echo -e "TLS证书:        已启用"
        if [ -n "$tls_cert_path" ]; then
            echo -e "证书文件:       ${tls_cert_path}"
        fi
    fi

    echo -e "\n${YELLOW}系统信息：${NC}"
    echo -e "内网IP:     ${host}"
    echo -e "系统架构:   $(uname -m) (识别为: ${arch})"
    echo -e "插件目录:   ${PLUGINS_DIR}"
    echo -e "Chart目录:  ${DEPLOY_DIR}/chart/"

    echo -e "${BLUE}操作指南：${NC}"
    echo -e "1. 查看集群状态: kubectl get all -n $NAMESPACE"
    echo -e "2. 查看实时日志: kubectl logs -n $NAMESPACE -f deployment/$NAMESPACE"
    echo -e "3. 查看POD状态：kubectl get pods -n $NAMESPACE"
}

# 获取系统架构
get_architecture() {
    local arch=$(uname -m)
    case "$arch" in
        x86_64)  arch="x86" ;;
        aarch64) arch="arm" ;;
        *)
            echo -e "${RED}错误：不支持的架构 $arch${NC}" >&2
            return 1
            ;;
    esac
    echo -e "${GREEN}检测到系统架构：${arch} (原始标识: $(uname -m))${NC}" >&2
    echo "$arch"
}

# 自动检测业务网口
get_network_ip() {
    echo -e "${BLUE}自动检测业务网络接口 IP 地址...${NC}" >&2
    local timeout=20
    local start_time=$(date +%s)
    local interface=""
    local host=""

    # 查找可用的网络接口
    while [ $(( $(date +%s) - start_time )) -lt $timeout ]; do
        # 获取所有非虚拟接口（排除 lo, docker, veth 等）
        interfaces=$(ip -o link show | awk -F': ' '{print $2}' | grep -vE '^lo$|docker|veth|br-|virbr|tun')

        for intf in $interfaces; do
            # 检查接口状态是否为 UP
            if ip link show "$intf" | grep -q 'state UP'; then
                # 获取 IPv4 地址
                ip_addr=$(ip addr show "$intf" | grep -w inet | awk '{print $2}' | cut -d'/' -f1)
                if [ -n "$ip_addr" ]; then
                    interface=$intf
                    host=$ip_addr
                    break 2 # 跳出两层循环
                fi
            fi
        done
        sleep 1
    done

    if [ -z "$interface" ]; then
        echo -e "${RED}错误：未找到可用的业务网络接口${NC}" >&2
        exit 1
    fi

    echo -e "${GREEN}使用网络接口：${interface}，IP 地址：${host}${NC}" >&2
    echo "$host"
}

get_address_input() {
    # 如果命令行参数已经提供了地址，则直接使用，不进行交互式输入
    if [ -n "$eulercopilot_address" ]; then
        echo -e "${GREEN}使用命令行参数配置："
        echo "EulerCopilot地址: $eulercopilot_address"
        return
    fi

    # 从环境变量读取或使用默认值
    eulercopilot_address=${EULERCOPILOT_ADDRESS:-"http://127.0.0.1:30080"}

    # 非交互模式直接使用默认值
    if [ -t 0 ]; then  # 仅在交互式终端显示提示
        echo -e "${BLUE}请输入 EulerCopilot 前端访问URL（默认：$eulercopilot_address）：${NC}"
        read -p "> " input_euler
        [ -n "$input_euler" ] && eulercopilot_address=$input_euler
    fi

    echo -e "${GREEN}使用配置："
    echo "EulerCopilot地址: $eulercopilot_address"
    echo -e "${YELLOW}注意: 鉴权服务将自动检测并提供选择${NC}"
}

# 检测已部署的Authelia认证策略
detect_authelia_policy() {
    echo -e "${BLUE}检测已部署的Authelia认证策略...${NC}"
    
    # 首先尝试从配置文件读取
    local config_file="/tmp/authelia_auth_policy.conf"
    if [ -f "$config_file" ]; then
        source "$config_file"
        if [ -n "$AUTH_POLICY" ]; then
            auth_policy="$AUTH_POLICY"
            echo -e "${GREEN}从配置文件检测到认证策略：$auth_policy${NC}"
            return 0
        fi
    fi
    
    # 如果配置文件不存在，从Kubernetes ConfigMap检测
    if kubectl get configmap authelia-config -n euler-copilot &>/dev/null; then
        local default_policy
        default_policy=$(kubectl get configmap authelia-config -n euler-copilot -o yaml | grep -E "default_policy:" | awk '{print $2}' | head -1)
        
        if [ -n "$default_policy" ]; then
            auth_policy="$default_policy"
            echo -e "${GREEN}从ConfigMap检测到认证策略：$auth_policy${NC}"
        else
            # 默认策略
            auth_policy="one_factor"
            echo -e "${YELLOW}无法检测到认证策略，使用默认值：$auth_policy${NC}"
        fi
    else
        auth_policy="one_factor"
        echo -e "${YELLOW}未找到Authelia配置，使用默认认证策略：$auth_policy${NC}"
    fi
    
    return 0
}

# 选择兼容的认证策略
select_compatible_policy() {
    echo -e "${BLUE}根据已部署的Authelia服务选择兼容的认证策略...${NC}"
    
    if [ "$auth_policy" = "two_factor" ]; then
        echo -e "${YELLOW}检测到Authelia配置为双因子认证${NC}"
        echo -e "${BLUE}请选择EulerCopilot的认证策略：${NC}"
        echo "1) two_factor   - 双因子认证（与Authelia保持一致）"
        echo "2) one_factor   - 单因子认证（降级使用）"
        echo -n "请输入选项编号（1-2）: "
        
        local choice
        read -r choice
        
        case $choice in
            1)
                echo -e "${GREEN}选择双因子认证，与Authelia保持一致${NC}"
                ;;
            2)
                auth_policy="one_factor"
                echo -e "${YELLOW}选择单因子认证，将使用降级模式${NC}"
                ;;
            *)
                echo -e "${YELLOW}无效选择，默认使用双因子认证${NC}"
                ;;
        esac
    else
        echo -e "${GREEN}检测到Authelia配置为单因子认证，EulerCopilot将使用相同策略${NC}"
    fi
    
    return 0
}

# 使用新的authelia客户端管理工具创建OIDC客户端
create_authelia_client() {
    local client_manager="${DEPLOY_DIR}/scripts/9-other-script/authelia_client_manager.sh"
    
    echo -e "${BLUE}正在使用authelia客户端管理工具创建OIDC客户端...${NC}"
    
    # 检查客户端管理工具是否存在
    if [ ! -f "$client_manager" ]; then
        echo -e "${RED}错误：未找到authelia客户端管理工具: $client_manager${NC}"
        return 1
    fi
    
    # 确保脚本可执行
    chmod +x "$client_manager"
    
    # 检测并选择认证策略
    detect_authelia_policy
    select_compatible_policy
    
    # 生成客户端名称和重定向URI
    local client_name="EulerCopilot"
    local redirect_uri="${eulercopilot_address}/api/auth/login"
    
    echo -e "${BLUE}创建OIDC客户端配置：${NC}"
    echo -e "  客户端名称: $client_name"
    echo -e "  重定向URI: $redirect_uri"
    
    # 创建OIDC客户端
    local temp_output
    temp_output=$(mktemp)
    
    if "$client_manager" create "$client_name" "$redirect_uri" "" "" "$auth_policy" > "$temp_output" 2>&1; then
        # 从输出中提取客户端信息
        local output_content
        output_content=$(cat "$temp_output")
        
        # 提取client_id和client_secret
        client_id=$(echo "$output_content" | grep -oP 'Client ID:\s*\K[^\s]+' | head -1)
        client_secret=$(echo "$output_content" | grep -oP 'Client Secret:\s*\K[^\s]+' | head -1)
        
        rm -f "$temp_output"
        
        if [ -n "$client_id" ] && [ -n "$client_secret" ]; then
            echo -e "${GREEN}✓ OIDC客户端创建成功：${NC}"
            echo -e "  Client ID: $client_id"
            echo -e "  Client Secret: $client_secret"
            
            # 设置服务信息
            auth_service_type="authelia"
            # 优先使用用户输入的地址或从values.yaml获取已配置的地址
            if [ -z "$auth_service_address" ]; then
                # 尝试从values.yaml获取已配置的authelia地址
                local configured_address
                configured_address=$(grep -E "^\s*authelia:\s*https?://" "${DEPLOY_DIR}/chart/euler_copilot/values.yaml" 2>/dev/null | sed -E 's/^\s*authelia:\s*//' | tr -d '"' | head -1)
                if [ -n "$configured_address" ]; then
                    auth_service_address="$configured_address"
                    echo -e "${GREEN}使用已配置的authelia地址: $auth_service_address${NC}"
                else
                    # 使用统一的IP获取方法
                    local host_ip
                    host_ip=$(get_network_ip)
                    auth_service_address="https://${host_ip}:30091"
                    echo -e "${YELLOW}自动检测到authelia地址: $auth_service_address${NC}"
                fi
            else
                echo -e "${GREEN}使用指定的authelia地址: $auth_service_address${NC}"
            fi
            
            return 0
        else
            echo -e "${RED}错误：无法从客户端管理工具输出中提取客户端信息${NC}"
            echo -e "${YELLOW}脚本输出：${NC}"
            cat "$temp_output"
            rm -f "$temp_output"
            return 1
        fi
    else
        echo -e "${RED}错误：authelia客户端管理工具执行失败${NC}"
        cat "$temp_output"
        rm -f "$temp_output"
        return 1
    fi
}

get_client_info_auto() {
    # 获取用户输入地址
    get_address_input
    
    echo -e "${BLUE}正在自动获取认证信息...${NC}"
    
    # 如果用户通过命令行指定了认证服务，直接使用
    if [ -n "$auth_service_type" ] && [ -n "$auth_service_address" ]; then
        echo -e "${GREEN}使用命令行指定的认证服务：${auth_service_type} (${auth_service_address})${NC}"
        
        # 根据服务类型设置相应的配置
        if [ "$auth_service_type" = "authelia" ]; then
            # 使用authelia客户端管理工具创建客户端
            if create_authelia_client; then
                return 0
            else
                echo -e "${YELLOW}authelia客户端创建失败，尝试使用备用方法...${NC}"
            fi
        else
            # 对于authhub，需要设置默认的client_id和client_secret
            # 这些将通过Python脚本获取或使用默认值
            echo -e "${YELLOW}将使用通用脚本获取${auth_service_type}认证信息...${NC}"
        fi
    fi
    
    # 检测鉴权服务类型
    echo -e "${BLUE}检测已部署的鉴权服务...${NC}"
    
    # 检查authelia服务
    if kubectl get service authelia -n euler-copilot &>/dev/null; then
        echo -e "${GREEN}检测到authelia服务，使用authelia_automation.sh创建客户端${NC}"
        auth_service_type="authelia"
        
        # 获取authelia服务地址 - 优先使用用户输入或已配置的地址
        if [ -z "$auth_service_address" ]; then
            # 尝试从values.yaml获取已配置的authelia地址
            local configured_address
            configured_address=$(grep -E "^\s*authelia:\s*https?://" "${DEPLOY_DIR}/chart/euler_copilot/values.yaml" 2>/dev/null | sed -E 's/^\s*authelia:\s*//' | tr -d '"' | head -1)
            if [ -n "$configured_address" ]; then
                auth_service_address="$configured_address"
                echo -e "${GREEN}使用已配置的authelia地址: $auth_service_address${NC}"
            else
                # 使用统一的IP获取方法
                local host_ip
                host_ip=$(get_network_ip)
                auth_service_address="https://${host_ip}:30091"
                echo -e "${YELLOW}自动检测到authelia地址: $auth_service_address${NC}"
            fi
        else
            echo -e "${GREEN}使用指定的authelia地址: $auth_service_address${NC}"
        fi
        
        # 使用authelia_automation.sh创建客户端
        if create_authelia_client; then
            return 0
        else
            echo -e "${YELLOW}authelia客户端创建失败，尝试使用备用方法...${NC}"
        fi
    fi
    
    # 如果authelia方法失败，回退到原来的方法
    echo -e "${BLUE}使用通用脚本获取认证信息...${NC}"
    
    # 创建临时文件
    local temp_file
    temp_file=$(mktemp)
    
    # 使用新的多服务支持脚本
    local script_path="${DEPLOY_DIR}/scripts/9-other-script/get_client_credentials.py"
    
    # 检查新脚本是否存在，如果不存在则使用旧脚本
    if [ ! -f "$script_path" ]; then
        echo -e "${YELLOW}警告: 未找到新版脚本，使用旧版脚本${NC}"
        script_path="${DEPLOY_DIR}/scripts/9-other-script/get_client_id_and_secret.py"
    fi
    
    # 非交互式运行：使用echo "1"来自动选择第一个检测到的服务
    echo "1" | python3 "$script_path" "${eulercopilot_address}" > "$temp_file" 2>&1
    local exit_code=$?

    # 检查Python脚本执行结果
    if [ $exit_code -ne 0 ]; then
        echo -e "${RED}错误：认证信息获取失败${NC}"
        cat "$temp_file"
        rm -f "$temp_file"
        return 1
    fi

    # 提取凭证信息和服务信息
    local output
    output=$(cat "$temp_file")
    
    # 提取认证信息
    client_id=$(echo "$output" | grep -oP 'client_id:\s*\K\S+' | tail -1)
    client_secret=$(echo "$output" | grep -oP 'client_secret:\s*\K\S+' | tail -1)
    
    # 提取服务信息（用于显示）
    auth_service_type=$(echo "$output" | grep -oP '鉴权服务类型:\s*\K\S+' | tail -1)
    auth_service_address=$(echo "$output" | grep -oP '鉴权服务地址:\s*\K\S+' | tail -1)
    
    # 优化服务地址：优先使用用户输入或已配置的地址
    if [ "$auth_service_type" = "authhub" ] || [ "$auth_service_type" = "authHub" ]; then
        # 尝试从values.yaml获取已配置的authhub地址
        local configured_address
        configured_address=$(grep -E "^\s*authhub:\s*https?://" "${DEPLOY_DIR}/chart/euler_copilot/values.yaml" 2>/dev/null | sed -E 's/^\s*authhub:\s*//' | tr -d '"' | head -1)
        if [ -n "$configured_address" ]; then
            auth_service_address="$configured_address"
            echo -e "${GREEN}使用已配置的authhub地址: $auth_service_address${NC}"
        else
            echo -e "${YELLOW}使用脚本检测到的authhub地址: $auth_service_address${NC}"
        fi
    elif [ "$auth_service_type" = "authelia" ]; then
        # 尝试从values.yaml获取已配置的authelia地址
        local configured_address
        configured_address=$(grep -E "^\s*authelia:\s*https?://" "${DEPLOY_DIR}/chart/euler_copilot/values.yaml" 2>/dev/null | sed -E 's/^\s*authelia:\s*//' | tr -d '"' | head -1)
        if [ -n "$configured_address" ]; then
            auth_service_address="$configured_address"
            echo -e "${GREEN}使用已配置的authelia地址: $auth_service_address${NC}"
        else
            echo -e "${YELLOW}使用脚本检测到的authelia地址: $auth_service_address${NC}"
        fi
    fi
    
    # 清理临时文件
    rm -f "$temp_file"
    
    # 验证提取结果
    if [ -z "$client_id" ] || [ -z "$client_secret" ]; then
        echo -e "${RED}错误：无法从脚本输出中提取有效的认证信息${NC}"
        echo -e "${YELLOW}脚本输出：${NC}"
        echo "$output"
        return 1
    fi
    
    echo -e "${GREEN}✓ 成功获取认证信息：${NC}"
    echo -e "  鉴权服务类型: ${auth_service_type:-未知}"
    echo -e "  Client ID: ${client_id}"
    echo -e "  Client Secret: ${client_secret}"
    
    return 0
}

get_client_info_manual() {
    # 非交互模式直接使用默认值
    if [ -t 0 ]; then  # 仅在交互式终端显示提示
        echo -e "${BLUE}请输入 Client ID: 域名（端点信息：Client ID）： ${NC}"
        read -p "> " input_id
        [ -n "$input_id" ] && client_id=$input_id

        echo -e "${BLUE}请输入 Client Secret: 域名（端点信息：Client Secret）：${NC}"
        read -p "> " input_secret
        [ -n "$input_secret" ] && client_secret=$input_secret
    fi

    # 统一验证域名格式
    echo -e "${GREEN}使用配置："
    echo "Client ID: $client_id"
    echo "Client Secret: $client_secret"
}

check_directories() {
    echo -e "${BLUE}检查语义接口目录是否存在...${NC}" >&2

    # 定义父目录和子目录列表
    local REQUIRED_OWNER="root:root"

    # 检查并创建父目录
    if [ -d "${PLUGINS_DIR}" ]; then
        echo -e "${GREEN}目录已存在：${PLUGINS_DIR}${NC}" >&2
	# 检查当前权限
        local current_owner=$(stat -c "%u:%g" "${PLUGINS_DIR}" 2>/dev/null)
        if [ "$current_owner" != "$REQUIRED_OWNER" ]; then
            echo -e "${YELLOW}当前目录权限: ${current_owner}，正在修改为 ${REQUIRED_OWNER}...${NC}" >&2
            if chown root:root "${PLUGINS_DIR}"; then
                echo -e "${GREEN}目录权限已成功修改为 ${REQUIRED_OWNER}${NC}" >&2
            else
                echo -e "${RED}错误：无法修改目录权限到 ${REQUIRED_OWNER}${NC}" >&2
                exit 1
            fi
        else
            echo -e "${GREEN}目录权限正确（${REQUIRED_OWNER}）${NC}" >&2
        fi
    else
        if mkdir -p "${PLUGINS_DIR}"; then
            echo -e "${GREEN}目录已创建：${PLUGINS_DIR}${NC}" >&2
            chown root:root "${PLUGINS_DIR}"  # 设置父目录所有者
        else
            echo -e "${RED}错误：无法创建目录 ${PLUGINS_DIR}${NC}" >&2
            exit 1
        fi
    fi
}

uninstall_eulercopilot() {
    echo -e "${YELLOW}检查是否存在已部署的 EulerCopilot...${NC}" >&2

    # 删除 Helm Release: euler-copilot
    if helm list -n euler-copilot --short | grep -q '^euler-copilot$'; then
        echo -e "${GREEN}找到Helm Release: euler-copilot，开始清理...${NC}"
        if ! helm uninstall euler-copilot -n euler-copilot; then
            echo -e "${RED}错误：删除Helm Release euler-copilot 失败！${NC}" >&2
            return 1
        fi
    else
        echo -e "${YELLOW}未找到需要清理的Helm Release: euler-copilot${NC}"
    fi

    # 强制清理PVC（改进版本）
    echo -e "${BLUE}开始强制清理PVC...${NC}"
    local pvc_names=("framework-semantics-claim" "web-static")
    for pvc_name in "${pvc_names[@]}"; do
        if kubectl get pvc "$pvc_name" -n euler-copilot &>/dev/null; then
            echo -e "${GREEN}强制清理PVC: ${pvc_name}...${NC}"
            
            # 先尝试移除finalizer
            kubectl patch pvc "$pvc_name" -n euler-copilot -p '{"metadata":{"finalizers":null}}' 2>/dev/null || true
            
            # 强制删除PVC
            kubectl delete pvc "$pvc_name" -n euler-copilot --force --grace-period=0 2>/dev/null || true
            
            # 等待确认删除
            local timeout=30
            local count=0
            while kubectl get pvc "$pvc_name" -n euler-copilot &>/dev/null && [ $count -lt $timeout ]; do
                echo -e "${YELLOW}等待PVC ${pvc_name} 删除完成...${NC}"
                sleep 1
                ((count++))
            done
            
            if kubectl get pvc "$pvc_name" -n euler-copilot &>/dev/null; then
                echo -e "${YELLOW}警告：PVC ${pvc_name} 删除超时，但继续执行${NC}"
            else
                echo -e "${GREEN}PVC ${pvc_name} 删除成功${NC}"
            fi
        else
            echo -e "${YELLOW}未找到需要清理的PVC: ${pvc_name}${NC}"
        fi
    done

    # 清理可能存在的PV
    echo -e "${BLUE}检查并清理相关PV...${NC}"
    local pv_names=("framework-semantics" "web-static-pv")
    for pv_name in "${pv_names[@]}"; do
        if kubectl get pv "$pv_name" &>/dev/null; then
            echo -e "${GREEN}清理PV: ${pv_name}...${NC}"
            kubectl patch pv "$pv_name" -p '{"metadata":{"finalizers":null}}' 2>/dev/null || true
            kubectl delete pv "$pv_name" --force --grace-period=0 2>/dev/null || true
        fi
    done

    # 删除 Secret: euler-copilot-system
    local secret_name="euler-copilot-system"
    if kubectl get secret "$secret_name" -n euler-copilot &>/dev/null; then
        echo -e "${GREEN}找到Secret: ${secret_name}${NC}"
    
        # 询问用户是否要删除
        while true; do
            read -p "是否要清除之前的会话? (y/n): " answer
            case $answer in
                [Yy]* )
                    echo -e "${GREEN}开始清理...${NC}"
                    if ! kubectl delete secret "$secret_name" -n euler-copilot; then
                        echo -e "${RED}错误：删除Secret ${secret_name} 失败！${NC}" >&2
                        return 1
                    fi
                    break
                    ;;
                [Nn]* )
                    echo -e "${YELLOW}已跳过删除Secret: ${secret_name}${NC}"
                    break
                    ;;
                * )
                    echo "请输入 y 或 n"
                    ;;
            esac
        done
    else
        echo -e "${YELLOW}未找到需要清理的Secret: ${secret_name}${NC}"
    fi

    # 等待所有资源完全清理
    echo -e "${BLUE}等待资源完全清理...${NC}"
    sleep 5

    echo -e "${GREEN}资源清理完成${NC}"
}

# PVC冲突预检查机制
check_pvc_conflicts() {
    echo -e "${BLUE}检查PVC冲突...${NC}"
    
    local conflicts_found=false
    
    # 检查是否存在冲突的PVC绑定
    if kubectl get pvc web-static -n euler-copilot &>/dev/null; then
        local bound_pv=$(kubectl get pvc web-static -n euler-copilot -o jsonpath='{.spec.volumeName}' 2>/dev/null)
        if [ "$bound_pv" = "framework-semantics" ]; then
            echo -e "${YELLOW}检测到PVC冲突：web-static绑定到了framework-semantics PV${NC}"
            conflicts_found=true
        fi
    fi
    
    # 检查framework-semantics-claim是否绑定到错误的PV
    if kubectl get pvc framework-semantics-claim -n euler-copilot &>/dev/null; then
        local bound_pv=$(kubectl get pvc framework-semantics-claim -n euler-copilot -o jsonpath='{.spec.volumeName}' 2>/dev/null)
        local pv_size=$(kubectl get pv "$bound_pv" -o jsonpath='{.spec.capacity.storage}' 2>/dev/null)
        if [ "$pv_size" = "10Gi" ]; then
            echo -e "${YELLOW}检测到PVC冲突：framework-semantics-claim绑定到了10Gi的PV（应该是5Gi）${NC}"
            conflicts_found=true
        fi
    fi
    
    # 如果发现冲突，进行清理
    if [ "$conflicts_found" = true ]; then
        echo -e "${YELLOW}发现PVC冲突，正在自动清理...${NC}"
        
        # 强制清理冲突的PVC
        local pvc_names=("web-static" "framework-semantics-claim")
        for pvc_name in "${pvc_names[@]}"; do
            if kubectl get pvc "$pvc_name" -n euler-copilot &>/dev/null; then
                echo -e "${GREEN}清理冲突PVC: ${pvc_name}${NC}"
                kubectl patch pvc "$pvc_name" -n euler-copilot -p '{"metadata":{"finalizers":null}}' 2>/dev/null || true
                kubectl delete pvc "$pvc_name" -n euler-copilot --force --grace-period=0 2>/dev/null || true
            fi
        done
        
        # 清理相关的pod
        local framework_pod=$(kubectl get pods -n euler-copilot | grep framework | awk '{print $1}' | head -1)
        if [ -n "$framework_pod" ]; then
            echo -e "${GREEN}重启framework pod: ${framework_pod}${NC}"
            kubectl delete pod "$framework_pod" -n euler-copilot 2>/dev/null || true
        fi
        
        # 等待清理完成
        echo -e "${BLUE}等待冲突清理完成...${NC}"
        sleep 10
        
        echo -e "${GREEN}PVC冲突清理完成${NC}"
    else
        echo -e "${GREEN}未发现PVC冲突${NC}"
    fi
}

modify_yaml() {
    local host=$1
    local preserve_models=$2  # 新增参数，指示是否保留模型配置
    echo -e "${BLUE}开始修改YAML配置文件...${NC}" >&2

    # 构建参数数组
    local set_args=()

    # 添加其他必填参数
    set_args+=(
        "--set" "globals.arch=$arch"
        "--set" "domain.euler_copilot=${eulercopilot_address}"
    )
    
    # 根据检测到的认证服务类型设置相应的配置
    if [ "$auth_service_type" = "authelia" ]; then
        set_args+=(
            "--set" "login.provider=authelia"
            "--set" "login.authelia.url=${auth_service_address}"
            "--set" "login.authelia.client_id=${client_id}"
            "--set" "login.authelia.client_secret=${client_secret}"
            "--set" "domain.authelia=${auth_service_address}"
        )
        echo -e "${GREEN}配置认证服务类型: authelia (${auth_service_address})${NC}" >&2
    elif [ "$auth_service_type" = "authhub" ] || [ "$auth_service_type" = "authHub" ]; then
        set_args+=(
            "--set" "login.provider=authhub"
            "--set" "login.client.id=${client_id}"
            "--set" "login.client.secret=${client_secret}"
            "--set" "domain.authhub=${auth_service_address}"
        )
        echo -e "${GREEN}配置认证服务类型: ${auth_service_type} (${auth_service_address})${NC}" >&2
    else
        echo -e "${RED}错误：未知的认证服务类型: ${auth_service_type}${NC}" >&2
        exit 1
    fi

    # 如果启用了TLS，添加TLS相关配置
    if [ "$use_tls" = "true" ]; then
        set_args+=(
            "--set" "tls.enabled=true"
            "--set" "tls.secretName=eulercopilot-tls-secret"
        )
        echo -e "${GREEN}已启用TLS配置${NC}" >&2
    fi

    # 如果不需要保留模型配置，则添加模型相关的参数
    if [[ "$preserve_models" != [Yy]* ]]; then
        set_args+=(
	    "--set" "models.answer.provider=ollama"
            "--set" "models.answer.endpoint=http://$host:11434/v1"
            "--set" "models.answer.key=sk-123456"
            "--set" "models.answer.name=deepseek-llm-7b-chat:latest"
            "--set" "models.functionCall.provider=ollama"
            "--set" "models.embedding.provider=ollama"
            "--set" "models.embedding.endpoint=http://$host:11434/v1"
            "--set" "models.embedding.key=sk-123456"
            "--set" "models.embedding.name=bge-m3:latest"
        )
    fi

    # 调用Python脚本，传递所有参数
    python3 "${DEPLOY_DIR}/scripts/9-other-script/modify_eulercopilot_yaml.py" \
      "${DEPLOY_DIR}/chart/euler_copilot/values.yaml" \
      "${DEPLOY_DIR}/chart/euler_copilot/values.yaml" \
      "${set_args[@]}" || {
        echo -e "${RED}错误：YAML文件修改失败${NC}" >&2
        exit 1
    }
    echo -e "${GREEN}YAML文件修改成功！${NC}" >&2
}

# 检查目录
enter_chart_directory() {
    echo -e "${BLUE}进入Chart目录...${NC}" >&2
    cd "${DEPLOY_DIR}/chart/" || {
        echo -e "${RED}错误：无法进入Chart目录 ${DEPLOY_DIR}/chart/${NC}" >&2
        exit 1
    }
}

pre_install_checks() {
    # 检查kubectl和helm是否可用
    command -v kubectl >/dev/null 2>&1 || error_exit "kubectl未安装"
    command -v helm >/dev/null 2>&1 || error_exit "helm未安装"

    # 检查Kubernetes集群连接
    kubectl cluster-info >/dev/null 2>&1 || error_exit "无法连接到Kubernetes集群"

    # 检查必要的存储类
    kubectl get storageclasses >/dev/null 2>&1 || error_exit "无法获取存储类信息"
}

# 执行安装
execute_helm_install() {
    echo -e "${BLUE}开始部署EulerCopilot（架构: $arch）...${NC}" >&2

    enter_chart_directory
    helm upgrade --install $NAMESPACE -n $NAMESPACE ./euler_copilot --create-namespace || {
        echo -e "${RED}Helm 安装 EulerCopilot 失败！${NC}" >&2
        exit 1
    }
    echo -e "${GREEN}Helm安装 EulerCopilot 成功！${NC}" >&2
}

# 检查pod状态
check_pods_status() {
    echo -e "${BLUE}==> 等待初始化就绪（30秒）...${NC}" >&2
    sleep 30

    local timeout=300
    local start_time=$(date +%s)

    echo -e "${BLUE}开始监控Pod状态（总超时时间300秒）...${NC}" >&2

    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [ $elapsed -gt $timeout ]; then
            echo -e "${YELLOW}警告：部署超时！请检查以下资源：${NC}" >&2
            kubectl get pods -n $NAMESPACE -o wide
            echo -e "\n${YELLOW}建议检查：${NC}"
            echo "1. 查看未就绪Pod的日志: kubectl logs -n $NAMESPACE <pod-name>"
            echo "2. 检查PVC状态: kubectl get pvc -n $NAMESPACE"
            echo "3. 检查Service状态: kubectl get svc -n $NAMESPACE"
            return 1
        fi

        local not_running=$(kubectl get pods -n $NAMESPACE -o jsonpath='{range .items[*]}{.metadata.name} {.status.phase} {.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' \
            | awk '$2 != "Running" || $3 != "True" {print $1 " " $2}')

        if [ -z "$not_running" ]; then
            echo -e "${GREEN}所有Pod已正常运行！${NC}" >&2
            kubectl get pods -n $NAMESPACE -o wide
            return 0
        else
            echo "等待Pod就绪（已等待 ${elapsed} 秒）..."
            echo "当前未就绪Pod："
            echo "$not_running" | awk '{print "  - " $1 " (" $2 ")"}'
            sleep 10
        fi
    done
}

# 修改main函数
main() {
    parse_arguments "$@"
    
    pre_install_checks
    
    local arch host
    arch=$(get_architecture) || exit 1
    host=$(get_network_ip) || exit 1
    
    uninstall_eulercopilot
    
    # 检查PVC冲突（在重新部署前）
    check_pvc_conflicts
    
    if ! get_client_info_auto; then
        get_client_info_manual
    fi
    
    # 检查authelia的HTTPS要求
    check_authelia_https_requirements
    
    # 管理TLS证书
    manage_tls_certificates
    
    check_directories
    
    # 交互式提示优化
    if [ -t 0 ]; then
        echo -e "${YELLOW}是否保留现有的模型配置？${NC}"
        echo -e "  ${BLUE}Y) 保留现有配置${NC}"
        echo -e "  ${BLUE}n) 使用默认配置${NC}"
        while true; do
            read -p "请选择(Y/N): " input_preserve
            case "${input_preserve:-Y}" in
                [YyNn]) preserve_models=${input_preserve:-Y}; break ;;
                *) echo -e "${RED}无效输入，请选择Y或n${NC}" ;;
            esac
        done
    else
        preserve_models="N"
    fi
    
    echo -e "${BLUE}开始修改YAML配置...${NC}"
    modify_yaml "$host" "$preserve_models"
    
    # 创建TLS Secret（在Helm安装之前）
    create_tls_secret
    
    echo -e "${BLUE}开始Helm安装...${NC}"
    execute_helm_install
    
    if check_pods_status; then
        echo -e "${GREEN}所有组件已就绪!${NC}"
        show_success_message "$host" "$arch"
    else
	echo -e "${YELLOW}部分组件尚未就绪，建议进行排查!${NC}"
    fi
}

main "$@"
