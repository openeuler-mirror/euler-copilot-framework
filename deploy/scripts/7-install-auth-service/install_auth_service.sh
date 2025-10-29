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
AUTH_SERVICE=""
AUTH_ADDRESS=""
CLIENT_ID=""
CLIENT_SECRET=""
OIDC_HMAC_SECRET=""
SESSION_SECRET=""
STORAGE_ENCRYPTION_KEY=""
JWT_SECRET=""
RSA_PRIVATE_KEY=""
USE_TLS=""
TLS_CERT_PATH=""
TLS_KEY_PATH=""
AUTH_POLICY=""  # 新增：认证策略配置

# 打印帮助信息
print_help() {
    echo -e "${GREEN}用法: $0 [选项]"
    echo -e "选项:"
    echo -e "  --help                      显示帮助信息"
    echo -e "  --service <服务类型>        指定鉴权服务类型 (authhub|authelia)"
    echo -e "  --address <地址>            指定鉴权服务的访问地址"
    echo -e ""
    echo -e "示例:"
    echo -e "  $0 --service authhub --address http://myhost:30081"
    echo -e "  $0 --service authelia --address http://myhost:30091${NC}"
    exit 0
}

# 生成随机密钥
generate_random_secret() {
    local length=${1:-32}
    openssl rand -base64 $length | tr -d "=+/" | cut -c1-$length
}

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

# 生成RSA私钥
generate_rsa_private_key() {
    openssl genrsa -out /tmp/rsa_private.key 2048 2>/dev/null
    cat /tmp/rsa_private.key
    rm -f /tmp/rsa_private.key
}

# 生成Argon2id哈希密码
generate_argon2_hash() {
    local password="$1"
    echo -n "$password" | argon2 "$(openssl rand -base64 16)" -id -t 3 -m 16 -p 4 -l 32 | sed 's/^/\$argon2id\$v=19\$m=65536,t=3,p=4\$/' 2>/dev/null || {
        # 如果argon2命令不可用，使用预设的哈希值
        echo "\$argon2id\$v=19\$m=65536,t=3,p=4\$eHA4/xN5ZQB0Pl+Larrf8A\$M7+SLwWQymLJQjUfEf/zin+xAEQ1EW8IcHet6tFcBvo"
    }
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

create_namespace() {
    echo -e "${BLUE}==> 检查命名空间 euler-copilot...${NC}"
    if ! kubectl get namespace euler-copilot &> /dev/null; then
        kubectl create namespace euler-copilot || {
            echo -e "${RED}命名空间创建失败！${NC}"
            return 1
        }
        echo -e "${GREEN}命名空间创建成功${NC}"
    else
        echo -e "${YELLOW}命名空间已存在，跳过创建${NC}"
    fi
}

# 选择鉴权服务
select_auth_service() {
    if [ -n "$AUTH_SERVICE" ]; then
        echo -e "${GREEN}使用参数指定的鉴权服务：$AUTH_SERVICE${NC}"
        return 0
    fi

    echo -e "${BLUE}请选择要部署的鉴权服务：${NC}"
    echo "1) AuthHub"
    echo "2) Authelia"
    echo -n "请输入选项编号（1-2）: "
    
    local choice
    read -r choice
    
    case $choice in
        1)
            AUTH_SERVICE="authhub"
            echo -e "${GREEN}选择了 AuthHub${NC}"
            ;;
        2)
            AUTH_SERVICE="authelia"
            echo -e "${GREEN}选择了 Authelia${NC}"
            ;;
        *)
            echo -e "${RED}无效的选项，请输入1或2${NC}"
            return 1
            ;;
    esac
}

# 获取鉴权服务地址
get_auth_address() {
    local default_address
    
    if [ "$AUTH_SERVICE" = "authhub" ]; then
        default_address="http://127.0.0.1:30081"
    else
        default_address="http://127.0.0.1:30091"
    fi
    
    if [ -n "$AUTH_ADDRESS" ]; then
        echo -e "${GREEN}使用参数指定的鉴权服务地址：$AUTH_ADDRESS${NC}"
        return 0
    fi
    
    echo -e "${BLUE}请输入 ${AUTH_SERVICE} 的访问地址（IP或域名，直接回车使用默认值 ${default_address}）：${NC}"
    read -p "${AUTH_SERVICE} 地址: " AUTH_ADDRESS

    # 处理空输入情况
    if [[ -z "$AUTH_ADDRESS" ]]; then
        AUTH_ADDRESS="$default_address"
        echo -e "${GREEN}使用默认地址：${AUTH_ADDRESS}${NC}"
    else
        echo -e "${GREEN}输入地址：${AUTH_ADDRESS}${NC}"
    fi

    return 0
}

# 选择认证策略
select_auth_policy() {
    if [ -n "$AUTH_POLICY" ]; then
        echo -e "${GREEN}使用预设的认证策略：$AUTH_POLICY${NC}"
        return 0
    fi

    echo -e "${BLUE}请选择Authelia的认证策略：${NC}"
    echo "1) one_factor   - 单因子认证（仅用户名密码）"
    echo "2) two_factor   - 双因子认证（用户名密码 + TOTP/WebAuthn）"
    echo -n "请输入选项编号（1-2）: "
    
    local choice
    read -r choice
    
    case $choice in
        1)
            AUTH_POLICY="one_factor"
            echo -e "${GREEN}选择了单因子认证策略${NC}"
            ;;
        2)
            AUTH_POLICY="two_factor"
            echo -e "${GREEN}选择了双因子认证策略${NC}"
            echo -e "${YELLOW}注意：双因子认证需要用户配置TOTP应用或WebAuthn设备${NC}"
            ;;
        *)
            echo -e "${RED}无效的选项，默认使用单因子认证${NC}"
            AUTH_POLICY="one_factor"
            ;;
    esac
    
    return 0
}

# 交互式配置确认
configure_authelia_settings() {
    echo -e "${BLUE}==> 配置 Authelia 参数...${NC}"
    
    echo -e "${YELLOW}注意：OIDC客户端配置将在EulerCopilot部署时自动创建${NC}"
    
    # 认证策略配置
    select_auth_policy || exit 1
    
    # TLS配置
    echo -e "${BLUE}是否启用TLS？(y/N): ${NC}"
    read -p "" enable_tls
    if [[ "$enable_tls" =~ ^[Yy]$ ]]; then
        USE_TLS="true"
        echo -e "${BLUE}请选择TLS证书配置方式：${NC}"
        echo "1) 自动生成自签名证书"
        echo "2) 使用已有证书"
        read -p "请输入选项编号（1-2）: " tls_choice
        
        case $tls_choice in
            1)
                echo -e "${GREEN}将自动生成自签名证书${NC}"
                ;;
            2)
                echo -e "${BLUE}请输入证书文件路径：${NC}"
                read -p "证书路径: " TLS_CERT_PATH
                echo -e "${BLUE}请输入私钥文件路径：${NC}"
                read -p "私钥路径: " TLS_KEY_PATH
                
                if [[ ! -f "$TLS_CERT_PATH" ]] || [[ ! -f "$TLS_KEY_PATH" ]]; then
                    echo -e "${RED}错误：证书或私钥文件不存在！${NC}"
                    return 1
                fi
                ;;
            *)
                echo -e "${RED}无效的选项，将使用自签名证书${NC}"
                ;;
        esac
    else
        USE_TLS="false"
        echo -e "${YELLOW}将使用HTTP（不推荐用于生产环境）${NC}"
    fi
    
    # 生成其他密钥
    echo -e "${BLUE}正在生成安全密钥...${NC}"
    OIDC_HMAC_SECRET=$(generate_random_secret 32)
    SESSION_SECRET=$(generate_random_secret 32)
    STORAGE_ENCRYPTION_KEY=$(generate_random_secret 32)
    JWT_SECRET=$(generate_random_secret 32)
    RSA_PRIVATE_KEY=$(generate_rsa_private_key)
    
    echo -e "${GREEN}配置完成！${NC}"
    
    # 显示配置摘要
    echo -e "\n${BLUE}==> 配置摘要：${NC}"
    echo -e "TLS启用: ${USE_TLS}"
    if [[ "$USE_TLS" == "true" ]]; then
        if [[ -n "$TLS_CERT_PATH" ]]; then
            echo -e "证书路径: ${TLS_CERT_PATH}"
            echo -e "私钥路径: ${TLS_KEY_PATH}"
        else
            echo -e "证书类型: 自签名证书"
        fi
    fi
    echo -e "安全密钥: [已自动生成]"
    echo -e "OIDC客户端: [将在EulerCopilot部署时创建]"
    
    echo -e "\n${BLUE}确认以上配置？(Y/n): ${NC}"
    read -p "" confirm
    if [[ "$confirm" =~ ^[Nn]$ ]]; then
        echo -e "${YELLOW}配置已取消，请重新运行脚本${NC}"
        return 1
    fi
    
    return 0
}

# 生成自签名证书
generate_self_signed_cert() {
    local domain="$1"
    local cert_dir="/tmp/authelia-certs"
    
    echo -e "${BLUE}==> 生成自签名证书...${NC}"
    
    # 创建临时目录
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
keyUsage = digitalSignature, keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = $domain
DNS.2 = localhost
DNS.3 = *.local
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

    # 如果domain是IP地址，添加到IP列表
    if [[ "$domain" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "IP.3 = $domain" >> "$cert_dir/cert.conf"
    fi
    
    # 生成证书
    openssl req -new -x509 -key "$cert_dir/tls.key" -out "$cert_dir/tls.crt" -days 365 -config "$cert_dir/cert.conf" -extensions v3_req
    
    TLS_CERT_PATH="$cert_dir/tls.crt"
    TLS_KEY_PATH="$cert_dir/tls.key"
    
    echo -e "${GREEN}自签名证书生成完成${NC}"
    echo -e "证书路径: $TLS_CERT_PATH"
    echo -e "私钥路径: $TLS_KEY_PATH"
}

# 配置TLS证书Secret
configure_tls_secret() {
    if [[ "$USE_TLS" == "true" ]]; then
        echo -e "${BLUE}==> 配置TLS证书...${NC}"
        
        # 如果没有指定证书路径，生成自签名证书
        if [[ -z "$TLS_CERT_PATH" ]] || [[ -z "$TLS_KEY_PATH" ]]; then
            local domain
            domain=$(echo "$AUTH_ADDRESS" | sed -E 's|^https?://([^:/]+).*|\1|')
            generate_self_signed_cert "$domain"
        fi
        
        # 删除现有的TLS Secret（如果存在）
        kubectl delete secret authelia-tls-secret -n euler-copilot 2>/dev/null || true
        
        # 创建TLS Secret
        kubectl create secret tls authelia-tls-secret \
            --cert="$TLS_CERT_PATH" \
            --key="$TLS_KEY_PATH" \
            -n euler-copilot || {
            echo -e "${RED}创建TLS Secret失败！${NC}"
            return 1
        }
        
        echo -e "${GREEN}TLS证书配置完成${NC}"
    fi
}

# 清理现有资源
uninstall_auth_services() {
    echo -e "${BLUE}==> 清理现有鉴权服务资源...${NC}"

    local RELEASES
    RELEASES=$(helm list -n euler-copilot --short | grep -E "(authhub|authelia)" || true)

    if [ -n "$RELEASES" ]; then
        echo -e "${YELLOW}找到以下Helm Release，开始清理...${NC}"
        for release in $RELEASES; do
            echo -e "${BLUE}正在删除Helm Release: ${release}${NC}"
            helm uninstall "$release" -n euler-copilot || echo -e "${RED}删除Helm Release失败，继续执行...${NC}"
        done
    else
        echo -e "${YELLOW}未找到需要清理的鉴权服务Helm Release${NC}"
    fi

    # 强制删除相关Pod
    echo -e "${YELLOW}强制删除相关Pod...${NC}"
    local pods
    pods=$(kubectl get pods -n euler-copilot | grep -E "(authelia|authhub|mysql)" | awk '{print $1}' || true)
    
    if [ -n "$pods" ]; then
        echo -e "${YELLOW}找到以下Pod，开始强制删除...${NC}"
        for pod in $pods; do
            echo -e "${BLUE}强制删除Pod: ${pod}${NC}"
            kubectl delete pod "$pod" -n euler-copilot --force --grace-period=0 || echo -e "${RED}Pod删除失败，继续执行...${NC}"
        done
    else
        echo -e "${YELLOW}未找到需要删除的Pod${NC}"
    fi

    # 清理PVC
    local pvc_list
    pvc_list=$(kubectl get pvc -n euler-copilot | grep -E "(mysql-pvc|authelia.*data)" 2>/dev/null || true)

    if [ -n "$pvc_list" ]; then
        echo -e "${YELLOW}找到以下PVC，开始清理...${NC}"
        kubectl get pvc -n euler-copilot | grep -E "(mysql-pvc|authelia.*data)" | awk '{print $1}' | while read pvc; do
            # 移除finalizers（如果存在）
            kubectl patch pvc "$pvc" -n euler-copilot -p '{"metadata":{"finalizers":null}}' 2>/dev/null || true
            # 强制删除PVC
            kubectl delete pvc "$pvc" -n euler-copilot --force --grace-period=0 || echo -e "${RED}PVC删除失败，继续执行...${NC}"
        done
    else
        echo -e "${YELLOW}未找到需要清理的PVC${NC}"
    fi

    # 清理Secrets
    local secret_list=("authhub-secret")
    for secret in "${secret_list[@]}"; do
        if kubectl get secret "$secret" -n euler-copilot &>/dev/null; then
            echo -e "${YELLOW}找到Secret: ${secret}，开始清理...${NC}"
            kubectl delete secret "$secret" -n euler-copilot || echo -e "${RED}删除Secret失败，继续执行...${NC}"
        fi
    done

    echo -e "${GREEN}资源清理完成${NC}"
}

# 保存认证策略配置
save_auth_policy_config() {
    local config_file="/tmp/authelia_auth_policy.conf"
    echo "AUTH_POLICY=$AUTH_POLICY" > "$config_file"
    echo "AUTH_SERVICE=$AUTH_SERVICE" >> "$config_file"
    echo "AUTH_ADDRESS=$AUTH_ADDRESS" >> "$config_file"
    echo -e "${GREEN}认证策略配置已保存到 $config_file${NC}"
}

# 安装AuthHub
install_authhub() {
    local arch="$1"
    echo -e "${BLUE}==> 安装 AuthHub...${NC}"
    
    helm upgrade --install authhub -n euler-copilot "${CHART_DIR}/authhub" \
        --set globals.arch="$arch" \
        --set domain.authhub="${AUTH_ADDRESS}" || {
        echo -e "${RED}Helm 安装 authhub 失败！${NC}"
        return 1
    }
    
    echo -e "${GREEN}AuthHub 安装完成！${NC}"
    echo -e "${GREEN}登录地址: ${AUTH_ADDRESS}${NC}"
    echo -e "${GREEN}默认账号密码: openEuler/changeme${NC}"
}

# 安装Authelia
install_authelia() {
    local arch="$1"
    echo -e "${BLUE}==> 安装 Authelia...${NC}"
    
    # 提取域名/IP用于会话配置
    local domain
    domain=$(echo "$AUTH_ADDRESS" | sed -E 's|^https?://([^:/]+).*|\1|')
    
    # 提取端口号用于NodePort配置
    local port
    port=$(echo "$AUTH_ADDRESS" | sed -E 's|^https?://[^:]+:([0-9]+).*|\1|')
    # 如果没有端口号，使用默认端口
    if [[ "$port" == "$AUTH_ADDRESS" ]]; then
        if [[ "$AUTH_ADDRESS" =~ ^https:// ]]; then
            port="443"
        else
            port="80"
        fi
    fi
    
    # 准备Helm参数（提供最小OIDC配置，客户端将在EulerCopilot部署时添加）
    local helm_args=(
        --set globals.arch="$arch"
        --set domain.authelia="$AUTH_ADDRESS"
        --set authelia.service.nodePort="$port"
        --set authelia.config.session.domain="$domain"
        --set authelia.config.session.secret="$SESSION_SECRET"
        --set authelia.config.storage.encryption_key="$STORAGE_ENCRYPTION_KEY"
        --set authelia.config.access_control.default_policy="$AUTH_POLICY"
        --set authelia.config.identity_validation.reset_password.jwt_secret="$JWT_SECRET"
        --set authelia.config.identity_providers.oidc.hmac_secret="$OIDC_HMAC_SECRET"
        --set authelia.config.identity_providers.oidc.jwks[0].key_id="main-signing-key"
        --set authelia.config.identity_providers.oidc.jwks[0].algorithm="RS256"
        --set-string authelia.config.identity_providers.oidc.jwks[0].key="$RSA_PRIVATE_KEY"
        --set-string authelia.config.identity_providers.oidc.clients[0].client_id="placeholder-client"
        --set-string authelia.config.identity_providers.oidc.clients[0].client_name="Placeholder Client"
        --set-string authelia.config.identity_providers.oidc.clients[0].client_secret="\$plaintext\$placeholder-secret"
        --set authelia.config.identity_providers.oidc.clients[0].public=false
        --set authelia.config.identity_providers.oidc.clients[0].authorization_policy="$AUTH_POLICY"
        --set authelia.config.identity_providers.oidc.clients[0].redirect_uris[0]="http://placeholder.local/callback"
        --set authelia.config.identity_providers.oidc.clients[0].scopes[0]="openid"
        --set authelia.config.identity_providers.oidc.clients[0].response_types[0]="code"
        --set authelia.config.identity_providers.oidc.clients[0].grant_types[0]="authorization_code"
        --set authelia.config.identity_providers.oidc.clients[0].response_modes[0]="query"
    )
    
    # 如果启用TLS，添加TLS相关配置
    if [[ "$USE_TLS" == "true" ]]; then
        helm_args+=(
            --set authelia.config.server.tls.enabled=true
            --set authelia.config.server.tls.certificate="/etc/authelia/certs/tls.crt"
            --set authelia.config.server.tls.key="/etc/authelia/certs/tls.key"
        )
    fi
    
    helm upgrade --install authelia -n euler-copilot "${CHART_DIR}/authelia" "${helm_args[@]}" || {
        echo -e "${RED}Helm 安装 authelia 失败！${NC}"
        return 1
    }
    
    echo -e "${GREEN}Authelia 安装完成！${NC}"
    echo -e "${GREEN}登录地址: ${AUTH_ADDRESS}${NC}"
    echo -e "${GREEN}默认用户账号: openEuler/openEuler12#\$${NC}"
    echo -e "${YELLOW}重要提示：生产环境请修改默认密码和密钥！${NC}"
}

# Helm安装
helm_install() {
    local arch="$1"
    echo -e "${BLUE}==> 进入部署目录...${NC}"
    [ ! -d "${CHART_DIR}" ] && {
        echo -e "${RED}错误：部署目录不存在 ${CHART_DIR} ${NC}"
        return 1
    }
    cd "${CHART_DIR}"

    case "$AUTH_SERVICE" in
        "authhub")
            install_authhub "$arch"
            ;;
        "authelia")
            install_authelia "$arch"
            ;;
        *)
            echo -e "${RED}错误：未知的鉴权服务类型 $AUTH_SERVICE${NC}"
            return 1
            ;;
    esac
}

check_auth_pods_status() {
    echo -e "${BLUE}==> 等待认证服务初始化就绪（30秒）...${NC}" >&2
    sleep 30

    local timeout=300
    local start_time=$(date +%s)

    echo -e "${BLUE}开始监控${AUTH_SERVICE}服务Pod状态（总超时时间300秒）...${NC}" >&2

    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [ $elapsed -gt $timeout ]; then
            echo -e "${YELLOW}警告：部署超时！请检查以下资源：${NC}" >&2
            kubectl get pods -n euler-copilot -o wide
            echo -e "\n${YELLOW}建议检查：${NC}"
            echo "1. 查看未就绪Pod的日志: kubectl logs -n euler-copilot <pod-name>"
            echo "2. 检查PVC状态: kubectl get pvc -n euler-copilot"
            echo "3. 检查Service状态: kubectl get svc -n euler-copilot"
            return 1
        fi

        # 统一检查euler-copilot命名空间下所有Pod的状态
        local not_running=$(kubectl get pods -n euler-copilot -o jsonpath='{range .items[*]}{.metadata.name} {.status.phase} {.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' \
            | awk '$2 != "Running" || $3 != "True" {print $1 " " $2}')

        if [ -z "$not_running" ]; then
            echo -e "${GREEN}所有Pod已正常运行！${NC}" >&2
            kubectl get pods -n euler-copilot -o wide
            return 0
        else
            echo "等待Pod就绪（已等待 ${elapsed} 秒）..."
            echo "当前未就绪Pod："
            echo "$not_running" | awk '{print "  - " $1 " (" $2 ")"}'
            sleep 10
        fi
    done
}

# 更新euler-copilot配置
update_euler_copilot_config() {
    echo -e "${BLUE}==> 自动更新euler-copilot配置...${NC}"
    
    local update_script="${SCRIPT_PATH%/*}/../9-other-script/update_auth_config.sh"
    
    if [[ ! -f "$update_script" ]]; then
        echo -e "${YELLOW}警告：找不到配置更新脚本，请手动更新euler-copilot配置${NC}"
        return 0
    fi
    
    # 构建更新命令参数
    local update_args=(
        --auth-service "$AUTH_SERVICE"
        --auth-address "$AUTH_ADDRESS"
    )
    
    # 注意：OIDC客户端配置将在EulerCopilot部署时自动处理
    
    # 执行配置更新
    if "$update_script" "${update_args[@]}"; then
        echo -e "${GREEN}euler-copilot配置更新成功${NC}"
    else
        echo -e "${YELLOW}警告：配置更新失败，请手动更新配置${NC}"
        echo -e "手动更新命令："
        echo -e "${BLUE}$update_script ${update_args[*]}${NC}"
    fi
}

deploy() {
    local arch
    arch=$(get_architecture) || exit 1
    create_namespace || exit 1
    uninstall_auth_services || exit 1
    
    # 选择鉴权服务
    select_auth_service || exit 1
    
    # 获取鉴权服务地址
    get_auth_address || exit 1
    
    # 如果是Authelia，进行详细配置
    if [[ "$AUTH_SERVICE" == "authelia" ]]; then
        configure_authelia_settings || exit 1
        configure_tls_secret || exit 1
    fi
    
    helm_install "$arch" || exit 1
    check_auth_pods_status || {
        echo -e "${RED}部署失败：认证服务Pod状态检查未通过！${NC}"
        exit 1
    }

    # 保存认证策略配置
    save_auth_policy_config
    
    # 自动更新euler-copilot配置
    update_euler_copilot_config
    
    # 显示部署结果
    echo -e "\n${GREEN}========================="
    echo -e "鉴权服务 ($AUTH_SERVICE) 部署完成！"
    echo -e "查看pod状态：kubectl get pod -n euler-copilot"
    echo -e "服务访问地址: $AUTH_ADDRESS"
    
    if [[ "$AUTH_SERVICE" == "authelia" ]]; then
        echo -e "\n${BLUE}Authelia服务信息：${NC}"
        echo -e "Authorization URL: ${AUTH_ADDRESS}/api/oidc/authorization"
        echo -e "Token URL: ${AUTH_ADDRESS}/api/oidc/token"
        echo -e "User Info URL: ${AUTH_ADDRESS}/api/oidc/userinfo"
        echo -e "\n${YELLOW}注意：${NC}"
        echo -e "- 当前配置了占位符OIDC客户端（redirect_uri指向无效地址，无法实际使用）"
        echo -e "- 真实的OIDC客户端配置将在部署EulerCopilot时自动创建和替换"
        
        if [[ "$USE_TLS" == "true" ]]; then
            echo -e "\n${YELLOW}TLS证书信息：${NC}"
            echo -e "TLS已启用，请确保客户端信任证书"
            if [[ -n "$TLS_CERT_PATH" ]] && [[ "$TLS_CERT_PATH" == "/tmp/authelia-certs/tls.crt" ]]; then
                echo -e "自签名证书路径: $TLS_CERT_PATH"
                echo -e "建议将证书添加到客户端信任列表"
            fi
        fi
    fi
    
    echo -e "\n${YELLOW}重要提示：${NC}"
    echo -e "1. 认证服务基础配置已更新到euler-copilot配置中"
    echo -e "2. OIDC客户端将在部署EulerCopilot时自动创建和配置"
    echo -e "3. 部署EulerCopilot时请运行："
    echo -e "   ${BLUE}${SCRIPT_PATH%/*}/../8-install-EulerCopilot/install_eulercopilot.sh${NC}"
    echo -e "4. 可使用以下命令验证配置："
    echo -e "   ${BLUE}${SCRIPT_PATH%/*}/../9-other-script/update_auth_config.sh --validate${NC}"
    echo -e "=========================${NC}"
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help)
                print_help
                exit 0
                ;;
            --service)
                if [ -n "$2" ] && [[ "$2" =~ ^(authhub|authelia)$ ]]; then
                    AUTH_SERVICE="$2"
                    shift 2
                else
                    echo -e "${RED}错误：--service 需要提供有效参数 (authhub|authelia)${NC}" >&2
                    exit 1
                fi
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
            *)
                echo -e "${RED}未知参数: $1${NC}" >&2
                print_help
                exit 1
                ;;
        esac
    done
}

main() {
    parse_args "$@"
    deploy
}

trap 'echo -e "${RED}操作被中断！${NC}"; exit 1' INT
main "$@"
