#!/bin/bash

set -eo pipefail

# 颜色定义
RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
NC='\033[0m'

# 全局变量
NAMESPACE="euler-copilot"
AUTHELIA_POD=""
CONFIG_DIR="/etc/authelia"
USERS_FILE="$CONFIG_DIR/users.yml"
AUTHELIA_CONFIG_FILE="/app/configuration.yml"

# 打印帮助信息
print_help() {
    echo -e "${GREEN}Authelia 自动化管理脚本${NC}"
    echo -e "${GREEN}用法: $0 [命令] [选项]${NC}"
    echo ""
    echo -e "${BLUE}命令:${NC}"
    echo -e "  create-user <用户名> <密码> <邮箱> [组名]    创建新用户"
    echo -e "  change-password <用户名> <新密码>           修改用户密码"
    echo -e "  delete-user <用户名>                       删除用户"
    echo -e "  list-users                                 列出所有用户"
    echo -e "  create-oidc-client <客户端ID> <客户端名称> <重定向URI> [密钥]  创建OIDC客户端"
    echo -e "  update-oidc-client <客户端ID> [选项]       更新OIDC客户端配置"
    echo -e "  delete-oidc-client <客户端ID>              删除OIDC客户端"
    echo -e "  list-oidc-clients                          列出所有OIDC客户端"
    echo -e "  generate-keys                              生成OIDC所需的密钥"
    echo -e "  backup-config                              备份当前配置"
    echo -e "  restore-config <备份文件>                  恢复配置"
    echo -e "  restart-service                            重启Authelia服务"
    echo ""
    echo -e "${BLUE}示例:${NC}"
    echo -e "  # 创建用户"
    echo -e "  $0 create-user openEuler 'openEuler12#\$' openEuler@example.com admins"
    echo ""
    echo -e "  # 修改密码"
    echo -e "  $0 change-password openEuler 'newPassword123#\$'"
    echo ""
    echo -e "  # 创建OIDC客户端"
    echo -e "  $0 create-oidc-client euler-copilot 'Euler Copilot' 'http://127.0.0.1:30080/auth/callback'"
    echo ""
    echo -e "  # 生成密钥"
    echo -e "  $0 generate-keys"
    echo ""
}

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 获取Authelia Pod名称
get_authelia_pod() {
    AUTHELIA_POD=$(kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=authelia -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$AUTHELIA_POD" ]; then
        log_error "未找到Authelia Pod，请确保Authelia服务已正确部署"
        return 1
    fi
    
    log_info "找到Authelia Pod: $AUTHELIA_POD"
    return 0
}

# 在Authelia Pod中执行命令
exec_in_pod() {
    local cmd="$1"
    kubectl exec -n $NAMESPACE "$AUTHELIA_POD" -- sh -c "$cmd"
}

# 生成密码哈希
generate_password_hash() {
    local password="$1"
    local hash
    local output
    
    log_info "生成密码哈希..."
    
    # 执行命令并捕获输出
    output=$(exec_in_pod "authelia crypto hash generate argon2 --password \"$password\"" 2>/dev/null)
    
    # 从输出中提取Digest行的哈希值
    hash=$(echo "$output" | grep "^Digest:" | sed 's/^Digest: //')
    
    if [ -z "$hash" ]; then
        log_error "密码哈希生成失败"
        log_error "命令输出: $output"
        return 1
    fi
    
    echo "$hash"
}

# 检查用户是否存在
user_exists() {
    local username="$1"
    exec_in_pod "test -f $USERS_FILE && grep -q '^  $username:' $USERS_FILE" 2>/dev/null
}

# 创建用户
create_user() {
    local username="$1"
    local password="$2"
    local email="$3"
    local groups="${4:-admins}"
    
    if [ -z "$username" ] || [ -z "$password" ] || [ -z "$email" ]; then
        log_error "用户名、密码和邮箱不能为空"
        return 1
    fi
    
    log_info "创建用户: $username"
    
    # 检查用户是否已存在
    if user_exists "$username"; then
        log_error "用户 $username 已存在"
        return 1
    fi
    
    # 生成密码哈希
    local password_hash
    password_hash=$(generate_password_hash "$password")
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    # 创建用户配置
    local user_config="  $username:
    displayname: \"$username\"
    password: \"$password_hash\"
    email: $email
    groups:
      - $groups"
    
    # 检查用户文件是否存在
    if ! exec_in_pod "test -f $USERS_FILE"; then
        log_info "创建新的用户数据库文件"
        exec_in_pod "cat > $USERS_FILE << 'EOF'
users:
$user_config
EOF"
    else
        # 备份原文件
        exec_in_pod "cp $USERS_FILE ${USERS_FILE}.backup.\$(date +%Y%m%d_%H%M%S)"
        
        # 检查文件是否以 ... 结尾（YAML文档结束标记）
        local yaml_end_count
        yaml_end_count=$(exec_in_pod "tail -1 $USERS_FILE | grep -c '^\\.\\.\\.\$' 2>/dev/null || echo 0")
        
        if [ "$yaml_end_count" -eq 1 ]; then
            # 移除 ... 标记，添加用户，然后重新添加 ... 标记
            exec_in_pod "
            head -n -1 $USERS_FILE > /tmp/users_temp.yml
            cat >> /tmp/users_temp.yml << 'EOF'
$user_config
...
EOF
            mv /tmp/users_temp.yml $USERS_FILE
            "
        else
            # 直接添加用户配置
            exec_in_pod "
            cat >> $USERS_FILE << 'EOF'
$user_config
EOF
            "
        fi
    fi
    
    log_success "用户 $username 创建成功"
    log_info "邮箱: $email"
    log_info "组: $groups"
}

# 修改用户密码
change_password() {
    local username="$1"
    local new_password="$2"
    
    if [ -z "$username" ] || [ -z "$new_password" ]; then
        log_error "用户名和新密码不能为空"
        return 1
    fi
    
    log_info "修改用户 $username 的密码"
    
    # 检查用户是否存在
    if ! user_exists "$username"; then
        log_error "用户 $username 不存在"
        return 1
    fi
    
    # 生成新密码哈希
    local password_hash
    password_hash=$(generate_password_hash "$new_password")
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    # 更新密码
    exec_in_pod "
    sed -i '/^  $username:/,/^  [^[:space:]]/ {
        s|password: \".*\"|password: \"$password_hash\"|
    }' $USERS_FILE
    "
    
    log_success "用户 $username 密码修改成功"
}

# 删除用户
delete_user() {
    local username="$1"
    
    if [ -z "$username" ]; then
        log_error "用户名不能为空"
        return 1
    fi
    
    log_info "删除用户: $username"
    
    # 检查用户是否存在
    if ! user_exists "$username"; then
        log_error "用户 $username 不存在"
        return 1
    fi
    
    # 删除用户配置
    exec_in_pod "
    sed -i '/^  $username:/,/^  [^[:space:]]/{ /^  $username:/d; /^  [^[:space:]]/!d; }' $USERS_FILE
    "
    
    log_success "用户 $username 删除成功"
}

# 列出所有用户
list_users() {
    log_info "当前用户列表:"
    
    if ! exec_in_pod "test -f $USERS_FILE"; then
        log_warning "用户数据库文件不存在"
        return 0
    fi
    
    exec_in_pod "
    if [ -f $USERS_FILE ]; then
        grep '^  [^[:space:]]' $USERS_FILE | sed 's/://g' | sed 's/^  /- /'
    fi
    "
}

# 生成OIDC密钥
generate_oidc_keys() {
    log_info "生成OIDC密钥..."
    
    # 生成HMAC密钥
    local hmac_secret
    hmac_secret=$(exec_in_pod "authelia crypto rand --length 32 --charset alphanumeric")
    
    # 生成RSA密钥对
    exec_in_pod "authelia crypto pair rsa generate --bits 2048 --directory $CONFIG_DIR"
    
    # 读取生成的私钥
    local private_key
    private_key=$(exec_in_pod "cat $CONFIG_DIR/private.pem")
    
    log_success "OIDC密钥生成完成"
    echo -e "${YELLOW}HMAC Secret:${NC} $hmac_secret"
    echo -e "${YELLOW}RSA Private Key:${NC}"
    echo "$private_key"
    
    # 保存到临时文件供后续使用
    echo "$hmac_secret" > /tmp/authelia_hmac_secret
    echo "$private_key" > /tmp/authelia_private_key
    
    log_info "密钥已保存到临时文件: /tmp/authelia_hmac_secret, /tmp/authelia_private_key"
}

# 通过ConfigMap创建OIDC客户端
create_oidc_client_via_configmap() {
    local client_id="$1"
    local client_name="$2"
    local redirect_uri="$3"
    local client_secret="${4:-$(openssl rand -base64 32)}"
    
    if [ -z "$client_id" ] || [ -z "$client_name" ] || [ -z "$redirect_uri" ]; then
        log_error "客户端ID、名称和重定向URI不能为空"
        return 1
    fi
    
    log_info "通过ConfigMap创建OIDC客户端: $client_id"
    
    # 获取当前ConfigMap
    local temp_config="/tmp/authelia-config-$(date +%s).yaml"
    if ! kubectl get configmap authelia-config -n $NAMESPACE -o yaml > "$temp_config"; then
        log_error "无法获取authelia ConfigMap"
        return 1
    fi
    
    # 创建新的客户端配置
    local new_client_config="      - client_id: \"$client_id\"
        client_name: \"$client_name\"
        client_secret: \"$client_secret\"
        public: false
        authorization_policy: \"two_factor\"
        token_endpoint_auth_method: \"client_secret_basic\"
        require_pkce: true
        pkce_challenge_method: \"S256\"
        redirect_uris:
          - \"$redirect_uri\"
        scopes:
          - \"openid\"
          - \"profile\"
          - \"email\"
          - \"groups\"
        response_types:
          - \"code\"
        grant_types:
          - \"authorization_code\"
        response_modes:
          - \"query\"
          - \"form_post\"
        userinfo_signed_response_alg: \"none\"
        consent_mode: \"implicit\"
        pre_configured_consent_duration: \"1y\""
    
    # 使用sed替换现有客户端配置
    local updated_config="/tmp/authelia-config-updated-$(date +%s).yaml"
    
    # 提取现有配置并替换客户端部分
    python3 << EOF
import yaml
import sys

try:
    with open('$temp_config', 'r') as f:
        config = yaml.safe_load(f)
    
    # 获取现有的authelia.yml配置
    authelia_yml = config['data']['authelia.yml']
    
    # 解析YAML内容
    authelia_config = yaml.safe_load(authelia_yml)
    
    # 确保identity_providers.oidc.clients存在
    if 'identity_providers' not in authelia_config:
        authelia_config['identity_providers'] = {}
    if 'oidc' not in authelia_config['identity_providers']:
        authelia_config['identity_providers']['oidc'] = {}
    if 'clients' not in authelia_config['identity_providers']['oidc']:
        authelia_config['identity_providers']['oidc']['clients'] = []
    
    # 创建新客户端
    new_client = {
        'client_id': '$client_id',
        'client_name': '$client_name',
        'client_secret': '$client_secret',
        'public': False,
        'authorization_policy': 'two_factor',
        'token_endpoint_auth_method': 'client_secret_basic',
        'require_pkce': True,
        'pkce_challenge_method': 'S256',
        'redirect_uris': ['$redirect_uri'],
        'scopes': ['openid', 'profile', 'email', 'groups'],
        'response_types': ['code'],
        'grant_types': ['authorization_code'],
        'response_modes': ['query', 'form_post'],
        'userinfo_signed_response_alg': 'none',
        'consent_mode': 'implicit',
        'pre_configured_consent_duration': '1y'
    }
    
    # 检查客户端是否已存在，如果存在则替换，否则添加
    client_exists = False
    for i, client in enumerate(authelia_config['identity_providers']['oidc']['clients']):
        if client.get('client_id') == '$client_id':
            authelia_config['identity_providers']['oidc']['clients'][i] = new_client
            client_exists = True
            break
    
    if not client_exists:
        authelia_config['identity_providers']['oidc']['clients'].append(new_client)
    
    # 更新ConfigMap数据
    config['data']['authelia.yml'] = yaml.dump(authelia_config, default_flow_style=False, allow_unicode=True)
    
    # 保存更新后的ConfigMap
    with open('$updated_config', 'w') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    print("SUCCESS")
    
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
EOF
    
    local python_result=$?
    if [ $python_result -ne 0 ]; then
        log_error "配置更新失败"
        rm -f "$temp_config" "$updated_config"
        return 1
    fi
    
    # 应用更新后的ConfigMap
    if kubectl apply -f "$updated_config"; then
        log_success "ConfigMap更新成功"
        
        # 重启authelia deployment以加载新配置
        log_info "重启authelia服务以加载新配置..."
        kubectl rollout restart deployment/authelia -n $NAMESPACE
        
        # 等待重启完成
        log_info "等待authelia重启完成..."
        kubectl rollout status deployment/authelia -n $NAMESPACE --timeout=120s
        
        log_success "OIDC客户端 $client_id 创建成功"
        log_info "客户端名称: $client_name"
        log_info "客户端密钥: $client_secret"
        log_info "重定向URI: $redirect_uri"
        
        # 清理临时文件
        rm -f "$temp_config" "$updated_config"
        
        # 保存客户端信息到临时文件供其他脚本使用
        echo "Client ID: $client_id" > /tmp/authelia_oidc_client_info
        echo "Client Secret: $client_secret" >> /tmp/authelia_oidc_client_info
        echo "Redirect URI: $redirect_uri" >> /tmp/authelia_oidc_client_info
        
        return 0
    else
        log_error "ConfigMap应用失败"
        rm -f "$temp_config" "$updated_config"
        return 1
    fi
}

# 创建OIDC客户端（保持向后兼容）
create_oidc_client() {
    local client_id="$1"
    local client_name="$2"
    local redirect_uri="$3"
    local client_secret="${4:-$(openssl rand -base64 32)}"
    
    if [ -z "$client_id" ] || [ -z "$client_name" ] || [ -z "$redirect_uri" ]; then
        log_error "客户端ID、名称和重定向URI不能为空"
        return 1
    fi
    
    log_info "创建OIDC客户端: $client_id"
    
    # 优先尝试通过ConfigMap方式创建
    if create_oidc_client_via_configmap "$client_id" "$client_name" "$redirect_uri" "$client_secret"; then
        return 0
    fi
    
    log_warning "ConfigMap方式失败，尝试传统方式..."
    
    # 检查是否已有HMAC密钥
    local hmac_secret
    if [ -f "/tmp/authelia_hmac_secret" ]; then
        hmac_secret=$(cat /tmp/authelia_hmac_secret)
    else
        log_warning "未找到HMAC密钥，正在生成..."
        generate_oidc_keys > /dev/null
        hmac_secret=$(cat /tmp/authelia_hmac_secret)
    fi
    
    # 检查是否已有私钥
    local private_key
    if [ -f "/tmp/authelia_private_key" ]; then
        private_key=$(cat /tmp/authelia_private_key)
    else
        log_error "未找到RSA私钥，请先运行 generate-keys 命令"
        return 1
    fi
    
    # 创建OIDC配置
    local oidc_config="
identity_providers:
  oidc:
    hmac_secret: '$hmac_secret'
    issuer_private_key: |
$(echo "$private_key" | sed 's/^/      /')
    enable_client_debug_messages: false
    lifespans:
      access_token: 1h
      refresh_token: 90m
      id_token: 1h
      authorize_code: 1m
    jwks:
      - key_id: 'main-signing-key'
        algorithm: 'RS256'
        use: 'sig'
        key: |
$(echo "$private_key" | sed 's/^/          /')
    clients:
      - client_id: '$client_id'
        client_name: '$client_name'
        client_secret: '\$plaintext\$$client_secret'
        public: false
        authorization_policy: 'one_factor'
        redirect_uris:
          - '$redirect_uri'
        scopes:
          - 'openid'
          - 'profile'
          - 'email'
          - 'groups'
          - 'offline_access'
        response_types:
          - 'code'
        grant_types:
          - 'authorization_code'
          - 'refresh_token'
        response_modes:
          - 'form_post'
          - 'query'
        consent_mode: 'implicit'
        pre_configured_consent_duration: '1y'
        require_pkce: true
        pkce_challenge_method: 'S256'
"
    
    # 更新Authelia配置 - 添加OIDC配置
    exec_in_pod "
    # 备份原配置
    cp $AUTHELIA_CONFIG_FILE ${AUTHELIA_CONFIG_FILE}.backup.\$(date +%Y%m%d_%H%M%S)
    
    # 简单方法：在...之前添加OIDC配置
    head -n -1 $AUTHELIA_CONFIG_FILE > /tmp/config_temp.yml
    cat >> /tmp/config_temp.yml << 'EOF'
$oidc_config
...
EOF
    mv /tmp/config_temp.yml $AUTHELIA_CONFIG_FILE
    "
    
    log_success "OIDC客户端 $client_id 创建成功"
    log_info "客户端名称: $client_name"
    log_info "客户端密钥: $client_secret"
    log_info "重定向URI: $redirect_uri"
    
    # 保存客户端信息
    echo "Client ID: $client_id" >> /tmp/authelia_oidc_clients
    echo "Client Secret: $client_secret" >> /tmp/authelia_oidc_clients
    echo "---" >> /tmp/authelia_oidc_clients
}

# 列出OIDC客户端
list_oidc_clients() {
    log_info "当前OIDC客户端列表:"
    
    if ! exec_in_pod "test -f $AUTHELIA_CONFIG_FILE"; then
        log_warning "Authelia配置文件不存在"
        return 0
    fi
    
    exec_in_pod "
    if grep -q 'clients:' $AUTHELIA_CONFIG_FILE; then
        grep -A 20 'clients:' $AUTHELIA_CONFIG_FILE | grep 'client_id:' | sed 's/.*client_id: /- /' | sed \"s/'//g\"
    else
        echo '暂无OIDC客户端'
    fi
    "
}

# 备份配置
backup_config() {
    local backup_dir="/tmp/authelia_backup_$(date +%Y%m%d_%H%M%S)"
    
    log_info "备份Authelia配置到: $backup_dir"
    
    mkdir -p "$backup_dir"
    
    # 从Pod中复制配置文件
    kubectl cp "$NAMESPACE/$AUTHELIA_POD:$USERS_FILE" "$backup_dir/users_database.yml" 2>/dev/null || log_warning "用户数据库文件不存在，跳过备份"
    kubectl cp "$NAMESPACE/$AUTHELIA_POD:$AUTHELIA_CONFIG_FILE" "$backup_dir/configuration.yml" 2>/dev/null || log_warning "配置文件不存在，跳过备份"
    
    # 备份密钥文件
    kubectl cp "$NAMESPACE/$AUTHELIA_POD:$CONFIG_DIR/private.pem" "$backup_dir/private.pem" 2>/dev/null || log_warning "私钥文件不存在，跳过备份"
    kubectl cp "$NAMESPACE/$AUTHELIA_POD:$CONFIG_DIR/public.pem" "$backup_dir/public.pem" 2>/dev/null || log_warning "公钥文件不存在，跳过备份"
    
    log_success "配置备份完成: $backup_dir"
    echo "$backup_dir"
}

# 恢复配置
restore_config() {
    local backup_dir="$1"
    
    if [ -z "$backup_dir" ] || [ ! -d "$backup_dir" ]; then
        log_error "备份目录不存在: $backup_dir"
        return 1
    fi
    
    log_info "从备份恢复配置: $backup_dir"
    
    # 恢复配置文件
    if [ -f "$backup_dir/users_database.yml" ]; then
        kubectl cp "$backup_dir/users_database.yml" "$NAMESPACE/$AUTHELIA_POD:$USERS_FILE"
        log_info "用户数据库已恢复"
    fi
    
    if [ -f "$backup_dir/configuration.yml" ]; then
        kubectl cp "$backup_dir/configuration.yml" "$NAMESPACE/$AUTHELIA_POD:$AUTHELIA_CONFIG_FILE"
        log_info "主配置文件已恢复"
    fi
    
    if [ -f "$backup_dir/private.pem" ]; then
        kubectl cp "$backup_dir/private.pem" "$NAMESPACE/$AUTHELIA_POD:$CONFIG_DIR/private.pem"
        log_info "私钥文件已恢复"
    fi
    
    if [ -f "$backup_dir/public.pem" ]; then
        kubectl cp "$backup_dir/public.pem" "$NAMESPACE/$AUTHELIA_POD:$CONFIG_DIR/public.pem"
        log_info "公钥文件已恢复"
    fi
    
    log_success "配置恢复完成"
}

# 重启Authelia服务
restart_service() {
    log_info "重启Authelia服务..."
    
    kubectl rollout restart deployment/authelia -n $NAMESPACE
    
    log_info "等待服务重启完成..."
    kubectl rollout status deployment/authelia -n $NAMESPACE --timeout=300s
    
    log_success "Authelia服务重启完成"
}

# 主函数
main() {
    local command="$1"
    shift
    
    case "$command" in
        "create-user")
            get_authelia_pod || exit 1
            create_user "$@"
            ;;
        "change-password")
            get_authelia_pod || exit 1
            change_password "$@"
            ;;
        "delete-user")
            get_authelia_pod || exit 1
            delete_user "$@"
            ;;
        "list-users")
            get_authelia_pod || exit 1
            list_users
            ;;
        "create-oidc-client")
            get_authelia_pod || exit 1
            create_oidc_client "$@"
            ;;
        "list-oidc-clients")
            get_authelia_pod || exit 1
            list_oidc_clients
            ;;
        "generate-keys")
            get_authelia_pod || exit 1
            generate_oidc_keys
            ;;
        "backup-config")
            get_authelia_pod || exit 1
            backup_config
            ;;
        "restore-config")
            get_authelia_pod || exit 1
            restore_config "$@"
            ;;
        "restart-service")
            restart_service
            ;;
        "--help"|"help"|"")
            print_help
            ;;
        *)
            log_error "未知命令: $command"
            print_help
            exit 1
            ;;
    esac
}

# 设置中断处理
trap 'echo -e "${RED}操作被中断！${NC}"; exit 1' INT

# 执行主函数
main "$@"
