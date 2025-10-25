#!/bin/bash

set -eo pipefail

RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
NC='\033[0m'

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="${SCRIPT_DIR}/certs"

# 打印帮助信息
print_help() {
    echo -e "${GREEN}TLS证书管理工具"
    echo -e "用法: $0 [选项]"
    echo -e "选项:"
    echo -e "  --help                      显示帮助信息"
    echo -e "  --generate <域名>           生成自签名证书"
    echo -e "  --install <证书路径> <私钥路径>  安装已有证书"
    echo -e "  --list                      列出已有证书"
    echo -e "  --remove <证书名称>         删除指定证书"
    echo -e "  --verify <证书路径>         验证证书"
    echo -e ""
    echo -e "示例:"
    echo -e "  $0 --generate authelia.local"
    echo -e "  $0 --install /path/to/cert.crt /path/to/key.key"
    echo -e "  $0 --verify /path/to/cert.crt${NC}"
    exit 0
}

# 创建证书目录
create_cert_dir() {
    if [[ ! -d "$CERT_DIR" ]]; then
        mkdir -p "$CERT_DIR"
        echo -e "${GREEN}创建证书目录: $CERT_DIR${NC}"
    fi
}

# 生成自签名证书
generate_self_signed_cert() {
    local domain="$1"
    local cert_name="${domain//[^a-zA-Z0-9]/_}"
    local cert_path="$CERT_DIR/${cert_name}"
    
    if [[ -z "$domain" ]]; then
        echo -e "${RED}错误：请提供域名${NC}"
        return 1
    fi
    
    echo -e "${BLUE}==> 为域名 '$domain' 生成自签名证书...${NC}"
    
    create_cert_dir
    mkdir -p "$cert_path"
    
    # 生成私钥
    openssl genrsa -out "$cert_path/tls.key" 2048
    
    # 生成证书签名请求配置
    cat > "$cert_path/cert.conf" <<EOF
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
        echo "IP.3 = $domain" >> "$cert_path/cert.conf"
    fi
    
    # 生成证书
    openssl req -new -x509 -key "$cert_path/tls.key" -out "$cert_path/tls.crt" -days 365 -config "$cert_path/cert.conf" -extensions v3_req
    
    # 生成证书信息文件
    cat > "$cert_path/info.txt" <<EOF
证书名称: $cert_name
域名: $domain
生成时间: $(date)
证书路径: $cert_path/tls.crt
私钥路径: $cert_path/tls.key
有效期: 365天
EOF
    
    echo -e "${GREEN}自签名证书生成完成！${NC}"
    echo -e "证书路径: $cert_path/tls.crt"
    echo -e "私钥路径: $cert_path/tls.key"
    echo -e "配置文件: $cert_path/cert.conf"
    echo -e "证书信息: $cert_path/info.txt"
    
    # 显示证书信息
    echo -e "\n${BLUE}证书详细信息：${NC}"
    openssl x509 -in "$cert_path/tls.crt" -text -noout | grep -A 1 "Subject:"
    openssl x509 -in "$cert_path/tls.crt" -text -noout | grep -A 5 "X509v3 Subject Alternative Name:"
    
    return 0
}

# 安装已有证书
install_existing_cert() {
    local cert_file="$1"
    local key_file="$2"
    
    if [[ -z "$cert_file" ]] || [[ -z "$key_file" ]]; then
        echo -e "${RED}错误：请提供证书文件和私钥文件路径${NC}"
        return 1
    fi
    
    if [[ ! -f "$cert_file" ]]; then
        echo -e "${RED}错误：证书文件不存在: $cert_file${NC}"
        return 1
    fi
    
    if [[ ! -f "$key_file" ]]; then
        echo -e "${RED}错误：私钥文件不存在: $key_file${NC}"
        return 1
    fi
    
    echo -e "${BLUE}==> 安装已有证书...${NC}"
    
    # 验证证书和私钥匹配
    local cert_hash key_hash
    cert_hash=$(openssl x509 -noout -modulus -in "$cert_file" | openssl md5)
    key_hash=$(openssl rsa -noout -modulus -in "$key_file" | openssl md5)
    
    if [[ "$cert_hash" != "$key_hash" ]]; then
        echo -e "${RED}错误：证书和私钥不匹配！${NC}"
        return 1
    fi
    
    # 获取证书的CN作为名称
    local cn
    cn=$(openssl x509 -noout -subject -in "$cert_file" | sed -n 's/.*CN=\([^,]*\).*/\1/p' | tr -d ' ')
    local cert_name="${cn//[^a-zA-Z0-9]/_}"
    
    if [[ -z "$cert_name" ]]; then
        cert_name="imported_$(date +%Y%m%d_%H%M%S)"
    fi
    
    local cert_path="$CERT_DIR/${cert_name}"
    
    create_cert_dir
    mkdir -p "$cert_path"
    
    # 复制证书文件
    cp "$cert_file" "$cert_path/tls.crt"
    cp "$key_file" "$cert_path/tls.key"
    
    # 生成证书信息文件
    cat > "$cert_path/info.txt" <<EOF
证书名称: $cert_name
原始证书路径: $cert_file
原始私钥路径: $key_file
安装时间: $(date)
证书路径: $cert_path/tls.crt
私钥路径: $cert_path/tls.key
EOF
    
    echo -e "${GREEN}证书安装完成！${NC}"
    echo -e "证书名称: $cert_name"
    echo -e "证书路径: $cert_path/tls.crt"
    echo -e "私钥路径: $cert_path/tls.key"
    
    # 显示证书信息
    echo -e "\n${BLUE}证书详细信息：${NC}"
    openssl x509 -in "$cert_path/tls.crt" -text -noout | grep -A 2 "Subject:"
    openssl x509 -in "$cert_path/tls.crt" -text -noout | grep -A 2 "Validity"
    
    return 0
}

# 列出已有证书
list_certificates() {
    echo -e "${BLUE}==> 已安装的证书：${NC}"
    
    if [[ ! -d "$CERT_DIR" ]] || [[ -z "$(ls -A "$CERT_DIR" 2>/dev/null)" ]]; then
        echo -e "${YELLOW}未找到已安装的证书${NC}"
        return 0
    fi
    
    local count=0
    for cert_path in "$CERT_DIR"/*; do
        if [[ -d "$cert_path" ]] && [[ -f "$cert_path/tls.crt" ]]; then
            count=$((count + 1))
            local cert_name=$(basename "$cert_path")
            echo -e "\n${GREEN}[$count] $cert_name${NC}"
            
            if [[ -f "$cert_path/info.txt" ]]; then
                cat "$cert_path/info.txt" | sed 's/^/  /'
            else
                echo -e "  证书路径: $cert_path/tls.crt"
                echo -e "  私钥路径: $cert_path/tls.key"
            fi
            
            # 显示证书有效期
            local validity
            validity=$(openssl x509 -in "$cert_path/tls.crt" -noout -dates 2>/dev/null || echo "无法读取证书信息")
            echo -e "  有效期: $validity" | sed 's/^/  /'
        fi
    done
    
    if [[ $count -eq 0 ]]; then
        echo -e "${YELLOW}未找到有效的证书${NC}"
    fi
}

# 删除指定证书
remove_certificate() {
    local cert_name="$1"
    
    if [[ -z "$cert_name" ]]; then
        echo -e "${RED}错误：请提供证书名称${NC}"
        return 1
    fi
    
    local cert_path="$CERT_DIR/$cert_name"
    
    if [[ ! -d "$cert_path" ]]; then
        echo -e "${RED}错误：证书不存在: $cert_name${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}确认删除证书 '$cert_name'？(y/N): ${NC}"
    read -p "" confirm
    
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        rm -rf "$cert_path"
        echo -e "${GREEN}证书 '$cert_name' 已删除${NC}"
    else
        echo -e "${YELLOW}操作已取消${NC}"
    fi
}

# 验证证书
verify_certificate() {
    local cert_file="$1"
    
    if [[ -z "$cert_file" ]]; then
        echo -e "${RED}错误：请提供证书文件路径${NC}"
        return 1
    fi
    
    if [[ ! -f "$cert_file" ]]; then
        echo -e "${RED}错误：证书文件不存在: $cert_file${NC}"
        return 1
    fi
    
    echo -e "${BLUE}==> 验证证书: $cert_file${NC}"
    
    # 检查证书格式
    if ! openssl x509 -in "$cert_file" -noout 2>/dev/null; then
        echo -e "${RED}错误：无效的证书格式${NC}"
        return 1
    fi
    
    echo -e "${GREEN}证书格式有效${NC}"
    
    # 显示证书详细信息
    echo -e "\n${BLUE}证书详细信息：${NC}"
    openssl x509 -in "$cert_file" -text -noout
    
    # 检查证书是否过期
    if openssl x509 -in "$cert_file" -checkend 0 >/dev/null 2>&1; then
        echo -e "\n${GREEN}证书有效（未过期）${NC}"
    else
        echo -e "\n${RED}警告：证书已过期！${NC}"
    fi
    
    return 0
}

# 创建Kubernetes Secret
create_k8s_secret() {
    local cert_name="$1"
    local secret_name="$2"
    local namespace="${3:-euler-copilot}"
    
    if [[ -z "$cert_name" ]]; then
        echo -e "${RED}错误：请提供证书名称${NC}"
        return 1
    fi
    
    if [[ -z "$secret_name" ]]; then
        secret_name="$cert_name-tls-secret"
    fi
    
    local cert_path="$CERT_DIR/$cert_name"
    
    if [[ ! -d "$cert_path" ]] || [[ ! -f "$cert_path/tls.crt" ]] || [[ ! -f "$cert_path/tls.key" ]]; then
        echo -e "${RED}错误：证书不存在或不完整: $cert_name${NC}"
        return 1
    fi
    
    echo -e "${BLUE}==> 创建Kubernetes TLS Secret...${NC}"
    echo -e "证书名称: $cert_name"
    echo -e "Secret名称: $secret_name"
    echo -e "命名空间: $namespace"
    
    # 删除现有Secret（如果存在）
    kubectl delete secret "$secret_name" -n "$namespace" 2>/dev/null || true
    
    # 创建TLS Secret
    kubectl create secret tls "$secret_name" \
        --cert="$cert_path/tls.crt" \
        --key="$cert_path/tls.key" \
        -n "$namespace" || {
        echo -e "${RED}创建Kubernetes Secret失败！${NC}"
        return 1
    }
    
    echo -e "${GREEN}Kubernetes TLS Secret创建成功！${NC}"
    echo -e "使用方法："
    echo -e "  在Helm values中设置: authelia.config.server.tls.enabled=true"
    echo -e "  Secret名称: $secret_name"
}

# 解析命令行参数
parse_args() {
    if [[ $# -eq 0 ]]; then
        print_help
    fi
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help)
                print_help
                ;;
            --generate)
                if [[ -n "$2" ]]; then
                    generate_self_signed_cert "$2"
                    exit $?
                else
                    echo -e "${RED}错误：--generate 需要提供域名${NC}"
                    exit 1
                fi
                ;;
            --install)
                if [[ -n "$2" ]] && [[ -n "$3" ]]; then
                    install_existing_cert "$2" "$3"
                    exit $?
                else
                    echo -e "${RED}错误：--install 需要提供证书文件和私钥文件路径${NC}"
                    exit 1
                fi
                ;;
            --list)
                list_certificates
                exit 0
                ;;
            --remove)
                if [[ -n "$2" ]]; then
                    remove_certificate "$2"
                    exit $?
                else
                    echo -e "${RED}错误：--remove 需要提供证书名称${NC}"
                    exit 1
                fi
                ;;
            --verify)
                if [[ -n "$2" ]]; then
                    verify_certificate "$2"
                    exit $?
                else
                    echo -e "${RED}错误：--verify 需要提供证书文件路径${NC}"
                    exit 1
                fi
                ;;
            --create-secret)
                if [[ -n "$2" ]]; then
                    create_k8s_secret "$2" "$3" "$4"
                    exit $?
                else
                    echo -e "${RED}错误：--create-secret 需要提供证书名称${NC}"
                    exit 1
                fi
                ;;
            *)
                echo -e "${RED}未知参数: $1${NC}"
                print_help
                ;;
        esac
    done
}

main() {
    parse_args "$@"
}

trap 'echo -e "${RED}操作被中断！${NC}"; exit 1' INT
main "$@"
