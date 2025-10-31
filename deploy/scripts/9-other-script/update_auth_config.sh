#!/bin/bash

set -eo pipefail

RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
NC='\033[0m'

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")/chart"
VALUES_FILE="$CHART_DIR/euler_copilot/values.yaml"

# 生成UUID
generate_uuid() {
    # 尝试使用系统的uuidgen命令
    if command -v uuidgen >/dev/null 2>&1; then
        uuidgen | tr '[:upper:]' '[:lower:]'
    else
        # 如果没有uuidgen，使用openssl生成类似UUID的字符串
        printf '%08x-%04x-%04x-%04x-%012x\n' \
            $((RANDOM * RANDOM)) \
            $((RANDOM % 65536)) \
            $((RANDOM % 65536 | 16384)) \
            $((RANDOM % 65536 | 32768)) \
            $((RANDOM * RANDOM * RANDOM))
    fi
}

# 打印帮助信息
print_help() {
    echo -e "${GREEN}认证服务配置更新工具"
    echo -e "用法: $0 [选项]"
    echo -e "选项:"
    echo -e "  --help                          显示帮助信息"
    echo -e "  --auth-service <类型>           认证服务类型 (authhub|authelia)"
    echo -e "  --auth-address <地址>           认证服务的完整地址"
    echo -e "  --client-id <ID>                OIDC客户端ID（仅Authelia，留空自动生成UUID）"
    echo -e "  --client-secret <密钥>          OIDC客户端密钥（仅Authelia）"
    echo -e "  --generate-uuid                 生成新的UUID客户端ID"
    echo -e "  --show-config                   显示当前配置"
    echo -e "  --validate                      验证配置"
    echo -e ""
    echo -e "示例:"
    echo -e "  $0 --auth-service authelia --auth-address https://10.211.55.10:30091"
    echo -e "  $0 --auth-service authhub --auth-address http://192.168.1.100:30081"
    echo -e "  $0 --generate-uuid"
    echo -e "  $0 --show-config"
    echo -e "  $0 --validate${NC}"
    exit 0
}

# 检查文件是否存在
check_files() {
    if [[ ! -f "$VALUES_FILE" ]]; then
        echo -e "${RED}错误：找不到values.yaml文件: $VALUES_FILE${NC}"
        exit 1
    fi
}

# 显示当前配置
show_config() {
    echo -e "${BLUE}==> 当前认证服务配置：${NC}"
    
    if [[ -f "$VALUES_FILE" ]]; then
        echo -e "\n${GREEN}域名配置：${NC}"
        grep -A 10 "^domain:" "$VALUES_FILE" | grep -E "(euler_copilot|authhub|authelia):" || true
        
        echo -e "\n${GREEN}端口配置：${NC}"
        grep -A 5 "^ports:" "$VALUES_FILE" | grep -E "(authhub|authelia):" || true
        
        echo -e "\n${GREEN}登录提供者：${NC}"
        grep -A 15 "^login:" "$VALUES_FILE" | grep -E "(provider|client_id|client_secret):" || true
    else
        echo -e "${RED}找不到配置文件${NC}"
    fi
}

# 验证地址格式
validate_address() {
    local address="$1"
    
    if [[ ! "$address" =~ ^https?://[^/]+$ ]]; then
        echo -e "${RED}错误：地址格式不正确，应该是 http://host:port 或 https://host:port 格式${NC}"
        return 1
    fi
    
    return 0
}

# 提取地址信息
extract_address_info() {
    local address="$1"
    local protocol host port
    
    protocol=$(echo "$address" | sed -E 's|^(https?)://.*|\1|')
    host=$(echo "$address" | sed -E 's|^https?://([^:/]+).*|\1|')
    port=$(echo "$address" | sed -E 's|^https?://[^:]+:([0-9]+).*|\1|')
    
    # 如果没有端口，使用默认端口
    if [[ "$port" == "$address" ]]; then
        if [[ "$protocol" == "https" ]]; then
            port="443"
        else
            port="80"
        fi
    fi
    
    echo "$protocol $host $port"
}

# 更新values.yaml中的域名配置
update_domain_config() {
    local auth_service="$1"
    local auth_address="$2"
    
    echo -e "${BLUE}==> 更新域名配置...${NC}"
    
    # 使用更精确的sed更新配置（只匹配domain部分）
    case "$auth_service" in
        "authhub")
            # 只更新 domain 部分下的 authhub 配置
            sed -i '/^domain:/,/^[^[:space:]]/ { /^  authhub:/ s|^  authhub:.*|  authhub: '$auth_address'| }' "$VALUES_FILE"
            echo -e "${GREEN}已更新 domain.authhub = $auth_address${NC}"
            ;;
        "authelia")
            # 只更新 domain 部分下的 authelia 配置
            sed -i '/^domain:/,/^[^[:space:]]/ { /^  authelia:/ s|^  authelia:.*|  authelia: '$auth_address'| }' "$VALUES_FILE"
            echo -e "${GREEN}已更新 domain.authelia = $auth_address${NC}"
            ;;
        *)
            echo -e "${RED}错误：不支持的认证服务类型: $auth_service${NC}"
            return 1
            ;;
    esac
}

# 更新Authelia的OIDC配置
update_authelia_oidc_config() {
    local client_id="$1"
    local client_secret="$2"
    
    # 如果没有提供client_id，自动生成UUID
    if [[ -z "$client_id" ]]; then
        client_id=$(generate_uuid)
        echo -e "${YELLOW}未提供Client ID，自动生成UUID: $client_id${NC}"
    fi
    
    if [[ -n "$client_id" ]]; then
        # 只更新 login.authelia 部分下的 client_id
        sed -i '/^  authelia:/,/^[^[:space:]]/ { /^    client_id:/ s|^    client_id:.*|    client_id: '$client_id'| }' "$VALUES_FILE"
        echo -e "${GREEN}已更新 login.authelia.client_id = $client_id${NC}"
    fi
    
    if [[ -n "$client_secret" ]]; then
        # 只更新 login.authelia 部分下的 client_secret
        sed -i '/^  authelia:/,/^[^[:space:]]/ { /^    client_secret:/ s|^    client_secret:.*|    client_secret: '$client_secret'| }' "$VALUES_FILE"
        echo -e "${GREEN}已更新 login.authelia.client_secret = [已设置]${NC}"
    fi
}

# 验证配置
# 验证配置
validate_config() {
    echo -e "${BLUE}==> 验证配置...${NC}"
    
    local errors=0
    local warnings=0
    
    # 检查euler_copilot域名配置 - 改为警告而不是错误
    if ! grep -q "euler_copilot:" "$VALUES_FILE" || grep -q "euler_copilot: \"\"" "$VALUES_FILE" || grep -q "euler_copilot: http://127.0.0.1" "$VALUES_FILE"; then
        echo -e "${YELLOW}警告：euler_copilot域名未配置或使用默认值，将在部署EulerCopilot时自动配置${NC}"
        warnings=$((warnings + 1))
    fi
    
    # 检查登录提供者配置
    local provider
    provider=$(grep "provider:" "$VALUES_FILE" | head -1 | sed 's/.*provider: *//' | tr -d ' "')
    
    if [[ -z "$provider" ]]; then
        echo -e "${YELLOW}警告：登录提供者未配置，将在部署EulerCopilot时自动设置${NC}"
        warnings=$((warnings + 1))
    else
        case "$provider" in
            "authhub")
                if ! grep -q "authhub:" "$VALUES_FILE" || grep -q "authhub: \"\"" "$VALUES_FILE"; then
                    echo -e "${YELLOW}警告：使用authhub但未配置authhub域名，将使用自动构建的地址${NC}"
                    warnings=$((warnings + 1))
                fi
                ;;
            "authelia")
                if ! grep -q "authelia:" "$VALUES_FILE" || grep -q "authelia: \"\"" "$VALUES_FILE"; then
                    echo -e "${YELLOW}警告：使用authelia但未配置authelia域名，将使用自动构建的地址${NC}"
                    warnings=$((warnings + 1))
                fi
                if grep -q "client_secret: your-client-secret-here" "$VALUES_FILE"; then
                    echo -e "${YELLOW}警告：Authelia客户端密钥未更新，将在部署时自动生成${NC}"
                    warnings=$((warnings + 1))
                fi
                ;;
            *)
                echo -e "${RED}错误：未知的登录提供者: $provider${NC}"
                errors=$((errors + 1))
                ;;
        esac
    fi
    
    if [[ $errors -eq 0 ]]; then
        if [[ $warnings -eq 0 ]]; then
            echo -e "${GREEN}配置验证通过${NC}"
            return 0
        else
            echo -e "${YELLOW}配置验证完成，发现 $warnings 个警告（不影响基础部署）${NC}"
            return 0
        fi
    else
        echo -e "${RED}发现 $errors 个配置错误${NC}"
        return 1
    fi
}

# 生成配置建议
generate_config_suggestions() {
    local auth_service="$1"
    local auth_address="$2"
    
    echo -e "\n${BLUE}==> 配置建议：${NC}"
    
    case "$auth_service" in
        "authhub")
            echo -e "1. 确保AuthHub服务在 $auth_address 可访问"
            echo -e "2. 检查AuthHub的客户端ID和密钥配置"
            echo -e "3. 重新部署euler-copilot以应用新配置："
            echo -e "   ${YELLOW}helm upgrade euler-copilot $CHART_DIR/euler_copilot -n euler-copilot${NC}"
            ;;
        "authelia")
            echo -e "1. 确保Authelia服务在 $auth_address 可访问"
            echo -e "2. 确认OIDC客户端ID和密钥正确配置"
            echo -e "3. 检查Authelia的OIDC配置中的redirect_uris包含："
            local euler_copilot_domain
            euler_copilot_domain=$(grep "euler_copilot:" "$VALUES_FILE" | head -1 | sed 's/.*euler_copilot: *//')
            echo -e "   ${YELLOW}$euler_copilot_domain/api/auth/login${NC}"
            echo -e "4. 重新部署euler-copilot以应用新配置："
            echo -e "   ${YELLOW}helm upgrade euler-copilot $CHART_DIR/euler_copilot -n euler-copilot${NC}"
            ;;
    esac
}

# 主函数
main() {
    local auth_service=""
    local auth_address=""
    local client_id=""
    local client_secret=""
    local show_config_flag=false
    local validate_flag=false
    local generate_uuid_flag=false
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help)
                print_help
                ;;
            --auth-service)
                if [[ -n "$2" ]] && [[ "$2" =~ ^(authhub|authelia)$ ]]; then
                    auth_service="$2"
                    shift 2
                else
                    echo -e "${RED}错误：--auth-service 需要提供有效参数 (authhub|authelia)${NC}"
                    exit 1
                fi
                ;;
            --auth-address)
                if [[ -n "$2" ]]; then
                    auth_address="$2"
                    shift 2
                else
                    echo -e "${RED}错误：--auth-address 需要提供地址参数${NC}"
                    exit 1
                fi
                ;;
            --client-id)
                if [[ -n "$2" ]]; then
                    client_id="$2"
                    shift 2
                else
                    echo -e "${RED}错误：--client-id 需要提供参数${NC}"
                    exit 1
                fi
                ;;
            --client-secret)
                if [[ -n "$2" ]]; then
                    client_secret="$2"
                    shift 2
                else
                    echo -e "${RED}错误：--client-secret 需要提供参数${NC}"
                    exit 1
                fi
                ;;
            --show-config)
                show_config_flag=true
                shift
                ;;
            --validate)
                validate_flag=true
                shift
                ;;
            --generate-uuid)
                generate_uuid_flag=true
                shift
                ;;
            *)
                echo -e "${RED}未知参数: $1${NC}"
                print_help
                ;;
        esac
    done
    
    check_files
    
    # 处理不同的操作
    if [[ "$show_config_flag" == true ]]; then
        show_config
        return 0
    fi
    
    if [[ "$validate_flag" == true ]]; then
        validate_config
        return $?
    fi
    
    if [[ "$generate_uuid_flag" == true ]]; then
        local new_uuid
        new_uuid=$(generate_uuid)
        echo -e "${GREEN}生成的UUID: ${new_uuid}${NC}"
        echo -e "${BLUE}可以使用以下命令更新配置：${NC}"
        echo -e "./update_auth_config.sh --auth-service authelia --auth-address <地址> --client-id $new_uuid"
        return 0
    fi
    
    # 更新配置
    if [[ -n "$auth_service" ]] && [[ -n "$auth_address" ]]; then
        validate_address "$auth_address" || exit 1
        
        echo -e "${BLUE}==> 更新认证服务配置...${NC}"
        echo -e "认证服务类型: $auth_service"
        echo -e "认证服务地址: $auth_address"
        
        update_domain_config "$auth_service" "$auth_address" || exit 1
        
        if [[ "$auth_service" == "authelia" ]]; then
            update_authelia_oidc_config "$client_id" "$client_secret"
        fi
        
        echo -e "\n${GREEN}配置更新完成！${NC}"
        
        # 验证更新后的配置
        validate_config
        
        # 生成配置建议
        generate_config_suggestions "$auth_service" "$auth_address"
        
    else
        echo -e "${YELLOW}请提供认证服务类型和地址，或使用 --help 查看帮助${NC}"
        exit 1
    fi
}

trap 'echo -e "${RED}操作被中断！${NC}"; exit 1' INT
main "$@"
