#!/bin/bash

set -eo pipefail

RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
NC='\033[0m'

SCRIPT_PATH="$(
  cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1
  pwd
)/$(basename "${BASH_SOURCE[0]}")"

CHART_DIR="$(
  canonical_path=$(readlink -f "$SCRIPT_PATH" 2>/dev/null || echo "$SCRIPT_PATH")
  dirname "$(dirname "$(dirname "$canonical_path")")"
)/chart"

# 全局变量
AUTH_ADDRESS=""
ENABLE_TLS=false
TLS_MODE=""
CERT_PATH=""
KEY_PATH=""

# 打印帮助信息
print_help() {
    echo -e "${GREEN}用法: $0 [选项]"
    echo -e "选项:"
    echo -e "  --help                      显示帮助信息"
    echo -e "  --address <地址>            指定Authelia服务的访问地址"
    echo -e "  --enable-tls                启用TLS/HTTPS支持"
    echo -e "  --cert <证书路径>           指定TLS证书文件路径"
    echo -e "  --key <私钥路径>            指定TLS私钥文件路径"
    echo -e ""
    echo -e "示例:"
    echo -e "  # HTTP模式（测试环境）"
    echo -e "  $0 --address http://127.0.0.1:30091"
    echo -e ""
    echo -e "  # HTTPS Ingress模式（生产环境推荐）"
    echo -e "  $0 --address https://authelia.yourdomain.com"
    echo -e ""
    echo -e "注意：此脚本只安装基础的Authelia服务，用户和OIDC配置需要在部署完成后单独配置${NC}"
    exit 0
}

# 获取系统架构
get_architecture() {
    local arch=$(uname -m)
    case "$arch" in
        x86_64)
            arch="x86"
            ;;
        aarch64)
            arch="arm"
            ;;
        *)
            echo -e "${RED}错误：不支持的架构 $arch${NC}" >&2
            return 1
            ;;
    esac
    echo -e "${GREEN}检测到系统架构：$(uname -m)${NC}" >&2
    echo "$arch"
}

# 生成自签名证书
generate_self_signed_cert() {
    local domain="$1"
    local cert_dir="/tmp/authelia-certs"
    
    echo -e "${BLUE}==> 生成自签名证书...${NC}"
    
    # 创建证书目录
    mkdir -p "$cert_dir"
    
    # 生成私钥
    openssl genrsa -out "$cert_dir/tls.key" 2048
    
    # 生成证书签名请求配置
    cat > "$cert_dir/cert.conf" <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = CN
ST = Beijing
L = Beijing
O = Euler Copilot
OU = IT Department
CN = $domain

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = $domain
DNS.2 = localhost
DNS.3 = *.localhost
IP.1 = 127.0.0.1
IP.2 = ::1
EOF
    
    # 生成自签名证书
    openssl req -new -x509 -key "$cert_dir/tls.key" -out "$cert_dir/tls.crt" -days 365 -config "$cert_dir/cert.conf" -extensions v3_req
    
    CERT_PATH="$cert_dir/tls.crt"
    KEY_PATH="$cert_dir/tls.key"
    
    echo -e "${GREEN}自签名证书生成完成：${NC}"
    echo -e "${GREEN}  证书文件：$CERT_PATH${NC}"
    echo -e "${GREEN}  私钥文件：$KEY_PATH${NC}"
    echo -e "${YELLOW}  注意：这是自签名证书，浏览器会显示安全警告${NC}"
}

# 获取Authelia服务地址
get_auth_address() {
    local default_address="http://127.0.0.1:30091"
    
    if [ -n "$AUTH_ADDRESS" ]; then
        echo -e "${GREEN}使用参数指定的Authelia服务地址：$AUTH_ADDRESS${NC}"
        return 0
    fi
    
    echo -e "${BLUE}请输入Authelia的访问地址（IP或域名，直接回车使用默认值 ${default_address}）：${NC}"
    read -p "Authelia地址: " AUTH_ADDRESS

    # 处理空输入情况
    if [[ -z "$AUTH_ADDRESS" ]]; then
        AUTH_ADDRESS="$default_address"
        echo -e "${GREEN}使用默认地址：${AUTH_ADDRESS}${NC}"
    else
        echo -e "${GREEN}输入地址：${AUTH_ADDRESS}${NC}"
    fi

    return 0
}

# 配置TLS
configure_tls() {
    # 检查地址是否使用HTTPS
    if [[ "$AUTH_ADDRESS" =~ ^https:// ]]; then
        echo -e "${YELLOW}检测到HTTPS地址，需要配置TLS证书${NC}"
        ENABLE_TLS=true
        
        if [ -z "$CERT_PATH" ] || [ -z "$KEY_PATH" ]; then
            echo -e "${BLUE}HTTPS部署模式选择：${NC}"
            echo "1) Ingress模式 - 使用现有证书（推荐生产环境）"
            echo "2) NodePort + 自签名证书模式（测试环境）"
            echo "3) NodePort + 现有证书模式"
            read -p "请选择部署模式 (1-3): " https_mode
            
            case "$https_mode" in
                1)
                    echo -e "${GREEN}选择了Ingress模式${NC}"
                    TLS_MODE="ingress"
                    configure_ingress_tls
                    ;;
                2)
                    echo -e "${GREEN}选择了NodePort + 自签名证书模式${NC}"
                    TLS_MODE="nodeport-selfsigned"
                    # 提取域名用于证书生成
                    local domain=$(echo "$AUTH_ADDRESS" | sed -E 's|^https?://([^:/]+).*|\1|')
                    generate_self_signed_cert "$domain"
                    ;;
                3)
                    echo -e "${GREEN}选择了NodePort + 现有证书模式${NC}"
                    TLS_MODE="nodeport-existing"
                    configure_existing_cert
                    ;;
                *)
                    echo -e "${RED}无效选择，默认使用自签名证书模式${NC}"
                    TLS_MODE="nodeport-selfsigned"
                    local domain=$(echo "$AUTH_ADDRESS" | sed -E 's|^https?://([^:/]+).*|\1|')
                    generate_self_signed_cert "$domain"
                    ;;
            esac
        fi
    fi
}

# 配置Ingress TLS
configure_ingress_tls() {
    echo -e "${BLUE}Ingress模式配置说明：${NC}"
    echo -e "${YELLOW}请确保以下条件已满足：${NC}"
    echo "1. K8s集群已安装Ingress Controller（如nginx-ingress、traefik等）"
    echo "2. 域名DNS已正确解析到集群"
    echo "3. TLS证书已准备好并创建为Kubernetes Secret"
    echo ""
    
    local domain=$(echo "$AUTH_ADDRESS" | sed -E 's|^https?://([^:/]+).*|\1|')
    echo -e "${BLUE}检测到域名：${GREEN}$domain${NC}"
    
    echo -e "${YELLOW}TLS证书Secret配置：${NC}"
    echo "请确保已创建名为 'authelia-tls' 的TLS Secret，命令示例："
    echo "kubectl create secret tls authelia-tls \\"
    echo "  --cert=/path/to/your/cert.pem \\"
    echo "  --key=/path/to/your/key.pem \\"
    echo "  -n euler-copilot"
    echo ""
    
    read -p "是否已创建TLS Secret？(y/N): " secret_ready
    if [[ ! "$secret_ready" =~ ^[Yy]$ ]]; then
        echo -e "${RED}请先创建TLS Secret后再继续部署${NC}"
        exit 1
    fi
    
    # 验证Secret是否存在
    if ! kubectl get secret authelia-tls -n euler-copilot >/dev/null 2>&1; then
        echo -e "${RED}错误：未找到 'authelia-tls' Secret${NC}"
        echo -e "${YELLOW}请使用以下命令创建：${NC}"
        echo "kubectl create secret tls authelia-tls --cert=<cert-file> --key=<key-file> -n euler-copilot"
        exit 1
    fi
    
    echo -e "${GREEN}TLS Secret验证成功${NC}"
}

# 配置现有证书
configure_existing_cert() {
    echo -e "${BLUE}现有证书配置：${NC}"
    
    while true; do
        read -p "请输入证书文件路径: " cert_file
        if [ -f "$cert_file" ]; then
            CERT_PATH="$cert_file"
            echo -e "${GREEN}证书文件：$CERT_PATH${NC}"
            break
        else
            echo -e "${RED}证书文件不存在，请重新输入${NC}"
        fi
    done
    
    while true; do
        read -p "请输入私钥文件路径: " key_file
        if [ -f "$key_file" ]; then
            KEY_PATH="$key_file"
            echo -e "${GREEN}私钥文件：$KEY_PATH${NC}"
            break
        else
            echo -e "${RED}私钥文件不存在，请重新输入${NC}"
        fi
    done
}

# 创建TLS Secret
create_tls_secret() {
    if [ "$ENABLE_TLS" = true ] && [ -n "$CERT_PATH" ] && [ -n "$KEY_PATH" ]; then
        echo -e "${BLUE}==> 创建TLS Secret...${NC}"
        
        # 删除现有的secret（如果存在）
        kubectl delete secret authelia-tls-secret -n euler-copilot --ignore-not-found=true
        
        # 创建新的TLS secret
        kubectl create secret tls authelia-tls-secret \
            --cert="$CERT_PATH" \
            --key="$KEY_PATH" \
            -n euler-copilot || {
            echo -e "${RED}创建TLS Secret失败！${NC}"
            return 1
        }
        
        echo -e "${GREEN}TLS Secret创建成功${NC}"
    fi
}

# 安装基础Authelia
install_authelia() {
    local arch="$1"
    echo -e "${BLUE}==> 安装基础 Authelia 服务...${NC}"
    
    # 提取域名/IP用于会话配置
    local domain
    domain=$(echo "$AUTH_ADDRESS" | sed -E 's|^https?://([^:/]+).*|\1|')
    
    # 生成随机密钥
    local session_secret=$(openssl rand -base64 32)
    local storage_key=$(openssl rand -base64 32)
    local jwt_secret=$(openssl rand -base64 32)
    
    # 添加官方Authelia仓库（如果尚未添加）
    if ! helm repo list | grep -q "^authelia"; then
        echo -e "${BLUE}添加Authelia官方仓库...${NC}"
        helm repo add authelia https://charts.authelia.com
        helm repo update
    fi
    
    # 创建包含基础密钥的Secret
    echo -e "${BLUE}创建Authelia基础Secret...${NC}"
    kubectl create secret generic authelia-secrets -n euler-copilot \
        --from-literal=identity_validation.reset_password.jwt.hmac.key="$jwt_secret" \
        --from-literal=session.encryption.key="$session_secret" \
        --from-literal=storage.encryption.key="$storage_key" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # 从AUTH_ADDRESS中提取端口号用于NodePort
    local node_port
    if [[ "$AUTH_ADDRESS" =~ :([0-9]+)(/|$) ]]; then
        node_port="${BASH_REMATCH[1]}"
    else
        # 如果没有指定端口，使用默认的NodePort
        node_port="30091"
    fi
    
    # 创建基础配置的values文件
    local values_file="/tmp/authelia-basic-values.yaml"
    cat > "$values_file" <<EOF
configMap:
  # 基础访问控制 - 允许所有访问（后续可通过CLI配置）
  access_control:
    default_policy: bypass
  
  # 基础文件认证后端配置（使用默认用户，后续可通过CLI修改）
  authentication_backend:
    file:
      enabled: true
      path: /config/users_database.yml
  
  # 禁用OIDC（后续通过CLI配置）
  identity_providers:
    oidc:
      enabled: false
  
  # 基础会话配置
  session:
    cookies:
    - authelia_url: $AUTH_ADDRESS
      domain: $domain
  
  # 本地存储配置
  storage:
    local:
      enabled: true
  
  # 文件系统通知配置
  notifier:
    filesystem:
      enabled: true

# 基础服务配置
image:
  tag: 4.39.13
persistence:
  enabled: true
  size: 1Gi
pod:
  kind: Deployment
  replicas: 1
secret:
  existingSecret: authelia-secrets
service:
  nodePort: $node_port
  type: NodePort
EOF
    
    # 根据TLS模式添加相关配置
    if [ "$ENABLE_TLS" = true ]; then
        echo -e "${BLUE}配置HTTPS模式: $TLS_MODE${NC}"
        
        case "$TLS_MODE" in
            "ingress")
                # Ingress模式配置
                cat >> "$values_file" <<EOF

# Ingress配置
ingress:
  enabled: true
  tls:
    enabled: true
    secret: authelia-tls
  hosts:
  - $domain
service:
  type: ClusterIP
EOF
                echo -e "${GREEN}配置Ingress模式，域名: $domain${NC}"
                ;;
            "nodeport-selfsigned"|"nodeport-existing")
                # NodePort模式保持原有配置
                echo -e "${GREEN}配置NodePort + TLS模式${NC}"
                ;;
        esac
    fi
    
    # 执行helm安装
    helm upgrade --install authelia -n euler-copilot authelia/authelia -f "$values_file" || {
        echo -e "${RED}Helm 安装 authelia 失败！${NC}"
        return 1
    }
    
    echo -e "${GREEN}基础 Authelia 安装完成！${NC}"
    echo -e "${GREEN}访问地址: ${AUTH_ADDRESS}${NC}"
    
    echo -e "\n${BLUE}=== 后续配置说明 ===${NC}"
    echo -e "${YELLOW}Authelia 基础服务已安装，但用户和OIDC配置需要单独配置：${NC}"
    echo -e "1. 等待 framework 部署完成"
    echo -e "2. 进入 Authelia pod 执行以下命令配置用户："
    echo -e "   kubectl exec -it -n euler-copilot deployment/authelia -- authelia crypto hash generate argon2 --password 'your-password'"
    echo -e "3. 使用生成的哈希值创建用户配置文件"
    echo -e "4. 配置OIDC客户端"
    echo -e "5. 重启Authelia服务使配置生效"
    
    # 根据TLS模式显示不同提示
    if [ "$ENABLE_TLS" = true ]; then
        case "$TLS_MODE" in
            "ingress")
                echo -e "${BLUE}部署模式: Ingress + TLS${NC}"
                echo -e "${YELLOW}注意事项：${NC}"
                echo -e "  • 确保DNS已正确解析到集群"
                echo -e "  • 确保Ingress Controller正常运行"
                echo -e "  • TLS证书由Kubernetes Secret管理"
                ;;
            "nodeport-selfsigned")
                echo -e "${BLUE}部署模式: NodePort + 自签名证书${NC}"
                echo -e "${YELLOW}注意事项：${NC}"
                echo -e "  • 浏览器会显示安全警告，这是正常的"
                echo -e "  • 自签名证书位置: $CERT_PATH"
                echo -e "  • 仅适用于测试环境"
                ;;
            "nodeport-existing")
                echo -e "${BLUE}部署模式: NodePort + 现有证书${NC}"
                echo -e "${YELLOW}证书信息：${NC}"
                echo -e "  • 证书文件: $CERT_PATH"
                echo -e "  • 私钥文件: $KEY_PATH"
                ;;
        esac
    else
        echo -e "${BLUE}部署模式: HTTP (NodePort)${NC}"
        echo -e "${YELLOW}注意：HTTP模式仅适用于测试环境${NC}"
    fi
    
    # 清理临时文件
    if [ -f "$values_file" ]; then
        rm -f "$values_file"
        echo -e "${BLUE}临时配置文件已清理${NC}"
    fi
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help)
                print_help
                exit 0
                ;;
            --address)
                if [ -n "$2" ]; then
                    AUTH_ADDRESS="$2"
                    shift 2
                else
                    echo -e "${RED}错误：--address 需要提供一个参数${NC}" >&2
                    exit 1
                fi
                ;;
            --enable-tls)
                ENABLE_TLS=true
                shift
                ;;
            --cert)
                if [ -n "$2" ]; then
                    CERT_PATH="$2"
                    shift 2
                else
                    echo -e "${RED}错误：--cert 需要提供一个参数${NC}" >&2
                    exit 1
                fi
                ;;
            --key)
                if [ -n "$2" ]; then
                    KEY_PATH="$2"
                    shift 2
                else
                    echo -e "${RED}错误：--key 需要提供一个参数${NC}" >&2
                    exit 1
                fi
                ;;
            *)
                echo -e "${RED}未知参数: $1${NC}" >&2
                exit 1
                ;;
        esac
    done
}

# 主部署函数
deploy() {
    local arch
    arch=$(get_architecture) || exit 1
    
    # 获取Authelia服务地址
    get_auth_address || exit 1
    
    # 配置TLS
    configure_tls || exit 1
    
    # 创建TLS Secret（如果需要）
    create_tls_secret || exit 1
    
    # 安装基础Authelia
    install_authelia "$arch" || exit 1

    echo -e "\n${GREEN}========================="
    echo -e "基础 Authelia 部署完成！"
    echo -e "服务访问地址: $AUTH_ADDRESS"
    echo -e "=========================${NC}"
}

main() {
    parse_args "$@"
    deploy
}

trap 'echo -e "${RED}操作被中断！${NC}"; exit 1' INT
main "$@"
