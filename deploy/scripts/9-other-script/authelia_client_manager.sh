#!/bin/bash

# Authelia OIDC客户端动态管理工具
# 通过更新ConfigMap来实现客户端的动态注册

set -eo pipefail

# 颜色定义
RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
NC='\033[0m'

NAMESPACE="euler-copilot"
CONFIGMAP_NAME="authelia-config"

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

# 生成UUID格式的客户端ID
generate_client_id() {
    python3 -c "import uuid; print(str(uuid.uuid4()))"
}

# 生成客户端密钥
generate_client_secret() {
    python3 -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(64)))"
}

# 检查authelia服务是否存在
check_authelia_service() {
    if ! kubectl get service authelia -n "$NAMESPACE" &>/dev/null; then
        log_error "未找到authelia服务，请确保authelia已正确部署"
        return 1
    fi
    return 0
}

# 备份当前ConfigMap
backup_configmap() {
    local backup_file="/tmp/authelia-config-backup-$(date +%Y%m%d_%H%M%S).yaml"
    kubectl get configmap "$CONFIGMAP_NAME" -n "$NAMESPACE" -o yaml > "$backup_file"
    # 使用纯文本输出，避免颜色代码干扰
    echo "ConfigMap已备份到: $backup_file" >&2
    echo "$backup_file"
}

# 添加或更新OIDC客户端
add_or_update_client() {
    local client_id="$1"
    local client_name="$2"
    local client_secret="$3"
    local redirect_uri="$4"
    local auth_policy="${5:-two_factor}"  # 新增：认证策略参数，默认为two_factor
    
    if [ -z "$client_id" ] || [ -z "$client_name" ] || [ -z "$client_secret" ] || [ -z "$redirect_uri" ]; then
        log_error "参数不完整: client_id, client_name, client_secret, redirect_uri 都是必需的"
        return 1
    fi
    
    log_info "准备添加/更新OIDC客户端:"
    log_info "  Client ID: $client_id"
    log_info "  Client Name: $client_name"
    log_info "  Redirect URI: $redirect_uri"
    log_info "  Auth Policy: $auth_policy"
    log_info "  PKCE Required: false"
    
    # 备份ConfigMap
    local backup_file
    backup_file=$(backup_configmap)
    
    # 获取当前配置
    local current_config
    current_config=$(kubectl get configmap "$CONFIGMAP_NAME" -n "$NAMESPACE" -o jsonpath='{.data.authelia\.yml}')
    
    # 检查客户端是否已存在
    if echo "$current_config" | grep -q "client_id: \"$client_id\""; then
        log_info "客户端 $client_id 已存在，将更新配置"
        
        # 使用 Python 脚本精确更新现有客户端
        local updated_config
        updated_config=$(python3 << EOF
import yaml
import sys

try:
    # 解析当前配置
    config_yaml = '''$current_config'''
    config = yaml.safe_load(config_yaml)
    
    # 查找并更新现有客户端
    clients = config['identity_providers']['oidc']['clients']
    for i, client in enumerate(clients):
        if client.get('client_id') == '$client_id':
            # 更新客户端配置
            clients[i].update({
                'client_name': '$client_name',
                'client_secret': '$client_secret',
                'authorization_policy': '$auth_policy',
                'require_pkce': True,  # 确保 PKCE 设置正确
                'redirect_uris': ['$redirect_uri']
            })
            break
    
    # 输出更新后的配置
    print(yaml.dump(config, default_flow_style=False))
    
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
EOF
)
    else
        log_info "添加新的OIDC客户端（替换占位符客户端）"
        
        # 使用 Python 脚本精确控制客户端配置
        local updated_config
        updated_config=$(python3 << EOF
import yaml
import sys

try:
    # 解析当前配置
    config_yaml = '''$current_config'''
    config = yaml.safe_load(config_yaml)
    
    # 确保结构存在
    if 'identity_providers' not in config:
        config['identity_providers'] = {}
    if 'oidc' not in config['identity_providers']:
        config['identity_providers']['oidc'] = {}
    if 'clients' not in config['identity_providers']['oidc']:
        config['identity_providers']['oidc']['clients'] = []
    
    # 创建新的客户端配置
    new_client = {
        'client_id': '$client_id',
        'client_name': '$client_name',
        'client_secret': '$client_secret',
        'public': False,
        'authorization_policy': '$auth_policy',
        'token_endpoint_auth_method': 'client_secret_post',
        'require_pkce': True,  # 明确设置为 True
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
    
    # 检查是否存在占位符客户端，如果存在则替换，否则添加
    clients = config['identity_providers']['oidc']['clients']
    placeholder_found = False
    
    for i, client in enumerate(clients):
        if client.get('client_id') == 'placeholder-client':
            clients[i] = new_client
            placeholder_found = True
            break
    
    if not placeholder_found:
        # 检查是否已存在相同的客户端ID
        existing_found = False
        for i, client in enumerate(clients):
            if client.get('client_id') == '$client_id':
                clients[i] = new_client
                existing_found = True
                break
        
        if not existing_found:
            clients.append(new_client)
    
    # 输出更新后的配置
    print(yaml.dump(config, default_flow_style=False))
    
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
EOF
)
    fi
    
    # 验证生成的配置是否有效
    if [ -z "$updated_config" ]; then
        log_error "生成的配置为空，操作失败"
        return 1
    fi
    
    # 创建临时文件存储新配置
    local temp_file
    temp_file=$(mktemp)
    echo "$updated_config" > "$temp_file"
    
    # 验证 YAML 格式是否正确
    if ! python3 -c "import yaml; yaml.safe_load(open('$temp_file'))" 2>/dev/null; then
        log_error "生成的 YAML 配置格式不正确"
        rm -f "$temp_file"
        return 1
    fi
    
    # 使用更可靠的方法更新 ConfigMap
    # 创建新的 ConfigMap YAML 文件
    local new_configmap_file
    new_configmap_file=$(mktemp)
    
    # 获取当前 ConfigMap 的元数据
    kubectl get configmap "$CONFIGMAP_NAME" -n "$NAMESPACE" -o yaml | \
        sed '/^  resourceVersion:/d' | \
        sed '/^  uid:/d' | \
        sed '/^  creationTimestamp:/d' > "$new_configmap_file"
    
    # 使用 Python 脚本更新 ConfigMap 中的 authelia.yml
    python3 << EOF
import yaml
import sys

try:
    # 读取当前 ConfigMap
    with open('$new_configmap_file', 'r') as f:
        configmap = yaml.safe_load(f)
    
    # 读取新的 authelia.yml 内容
    with open('$temp_file', 'r') as f:
        new_authelia_config = f.read()
    
    # 更新 ConfigMap 中的 authelia.yml
    configmap['data']['authelia.yml'] = new_authelia_config
    
    # 写回 ConfigMap 文件
    with open('$new_configmap_file', 'w') as f:
        yaml.dump(configmap, f, default_flow_style=False)
    
    print("ConfigMap 文件更新成功")
    
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
EOF
    
    # 应用更新后的 ConfigMap
    if kubectl apply -f "$new_configmap_file"; then
        log_success "ConfigMap 更新成功"
        rm -f "$new_configmap_file"
    else
        log_error "ConfigMap 更新失败，正在恢复备份"
        kubectl apply -f "$backup_file"
        rm -f "$temp_file" "$new_configmap_file"
        return 1
    fi
    
    # 清理临时文件
    rm -f "$temp_file"
    
    log_success "ConfigMap更新成功"
    
    # 重启authelia以加载新配置
    log_info "重启authelia服务以加载新配置..."
    kubectl rollout restart deployment/authelia -n "$NAMESPACE"
    
    # 等待重启完成
    if kubectl rollout status deployment/authelia -n "$NAMESPACE" --timeout=120s; then
        log_success "authelia服务重启完成"
        log_success "OIDC客户端 $client_id 配置成功"
        
        # 输出客户端信息
        echo ""
        log_success "客户端信息:"
        echo "  Client ID: $client_id"
        echo "  Client Secret: $client_secret"
        echo "  Redirect URI: $redirect_uri"
        
        return 0
    else
        log_error "authelia服务重启失败"
        log_warning "正在恢复备份配置..."
        kubectl apply -f "$backup_file"
        return 1
    fi
}

# 创建新的OIDC客户端
create_client() {
    local client_name="$1"
    local redirect_uri="$2"
    local client_id="${3:-$(generate_client_id)}"
    local client_secret="${4:-$(generate_client_secret)}"
    local auth_policy="${5:-two_factor}"  # 新增：认证策略参数
    
    if [ -z "$client_name" ] || [ -z "$redirect_uri" ]; then
        log_error "用法: create_client <client_name> <redirect_uri> [client_id] [client_secret]"
        return 1
    fi
    
    add_or_update_client "$client_id" "$client_name" "$client_secret" "$redirect_uri" "$auth_policy"
}

# 显示帮助信息
show_help() {
    echo -e "${GREEN}Authelia OIDC客户端动态管理工具${NC}"
    echo ""
    echo -e "${BLUE}用法:${NC}"
    echo "  $0 create <client_name> <redirect_uri> [client_id] [client_secret]"
    echo "  $0 update <client_id> <client_name> <client_secret> <redirect_uri>"
    echo ""
    echo -e "${BLUE}示例:${NC}"
    echo "  # 创建新客户端（自动生成ID和密钥）"
    echo "  $0 create EulerCopilot https://10.211.55.10/api/auth/login"
    echo ""
    echo "  # 创建客户端（指定ID和密钥）"
    echo "  $0 create EulerCopilot https://10.211.55.10/api/auth/login my-client-id my-secret"
    echo ""
    echo "  # 更新现有客户端"
    echo "  $0 update existing-client-id EulerCopilot new-secret https://new-uri/callback"
}

# 主函数
main() {
    local command="$1"
    shift
    
    case "$command" in
        "create")
            check_authelia_service || exit 1
            create_client "$@"
            ;;
        "update")
            check_authelia_service || exit 1
            add_or_update_client "$@"
            ;;
        "--help"|"help"|"")
            show_help
            ;;
        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
