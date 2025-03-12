#!/bin/bash

GITHUB_MIRROR="https://gh-proxy.com"
ARCH=$(uname -m)

# 函数：显示帮助信息（更新版）
function help {
    echo -e "用法：bash install_tools.sh [cn: 可选镜像参数]"
    echo -e "示例：bash install_tools.sh       # 使用默认设置安装"
    echo -e "      bash install_tools.sh cn   # 使用国内镜像加速"
}

function check_user {
    if [[ $(id -u) -ne 0 ]]; then
        echo -e "\033[31m[Error]请以root权限运行该脚本！\033[0m"
        exit 1
    fi
}

function check_arch {
    case $ARCH in
        x86_64)  ARCH=amd64 ;;
        aarch64) ARCH=arm64 ;;
        *)
            echo -e "\033[31m[Error]当前CPU架构不受支持\033[0m"
            return 1
            ;;
    esac
    return 0
}

install_basic_tools() {
    # 安装基础工具
    echo "Installing tar, vim, curl, wget..."
    yum install -y tar vim curl wget

    # 检查 pip 是否已安装
    if ! command -v pip &> /dev/null; then
        echo "pip could not be found, installing python3-pip..."
        yum install -y python3-pip
    else
        echo "pip is already installed."
    fi

    # 使用 pip 安装 requests
    echo "Installing requests with pip..."
    pip install requests ruamel.yaml

    echo "All basic tools have been installed."
}

function install_k3s {
    local k3s_version="v1.30.2+k3s1"
    local image_name="k3s-airgap-images-$ARCH.tar.zst"
    
    # 根据架构确定二进制文件名
    local bin_name="k3s"
    [[ $ARCH == "arm64" ]] && bin_name="k3s-arm64"

    # 构建下载URL
    local k3s_bin_url="$GITHUB_MIRROR/https://github.com/k3s-io/k3s/releases/download/$k3s_version/$bin_name"
    local k3s_image_url="$GITHUB_MIRROR/https://github.com/k3s-io/k3s/releases/download/$k3s_version/$image_name"

    echo -e "[Info] 下载K3s二进制文件（版本：$k3s_version）"
    if ! curl -L "$k3s_bin_url" -o /usr/local/bin/k3s; then
        echo -e "\033[31m[Error] K3s二进制文件下载失败\033[0m"
        return 1
    fi
    chmod +x /usr/local/bin/k3s

    echo -e "[Info] 下载K3s依赖镜像"
    mkdir -p /var/lib/rancher/k3s/agent/images
    if ! curl -L "$k3s_image_url" -o "/var/lib/rancher/k3s/agent/images/$image_name"; then
        echo -e "\033[31m[Error] K3s依赖下载失败\033[0m"
        return 1
    fi

    # 选择安装源
    local install_source="https://get.k3s.io"
    [[ $1 == "cn" ]] && install_source="https://rancher-mirror.rancher.cn/k3s/k3s-install.sh"

    echo -e "[Info] 执行K3s安装脚本"
    if ! curl -sfL "$install_source" | INSTALL_K3S_SKIP_DOWNLOAD=true sh -; then
        echo -e "\033[31m[Error] K3s安装失败\033[0m"
        return 1
    fi

    echo -e "\033[32m[Success] K3s ($k3s_version) 安装成功\033[0m"
    return 0
}

function install_helm {
    local helm_version="v3.15.3"
    local file_name="helm-${helm_version}-linux-${ARCH}.tar.gz"
    
    # 根据镜像参数选择下载源
    local base_url="https://get.helm.sh"
    [[ $1 == "cn" ]] && base_url="https://kubernetes.oss-cn-hangzhou.aliyuncs.com/charts/helm/v${helm_version#v}"

    echo -e "[Info] 下载Helm（版本：$helm_version）"
    if ! curl -L "$base_url/$file_name" -o "$file_name"; then
        echo -e "\033[31m[Error] Helm下载失败\033[0m"
        return 1
    fi

    echo -e "[Info] 解压并安装Helm"
    tar -zxvf "$file_name" --strip-components 1 -C /usr/local/bin "linux-$ARCH/helm"
    chmod +x /usr/local/bin/helm
    rm -f "$file_name"

    echo -e "\033[32m[Success] Helm ($helm_version) 安装成功\033[0m"
    return 0
}

function set_kubeconfig() {
    local bashrc_file="/root/.bashrc"
    local kubeconfig_line="export KUBECONFIG=/etc/rancher/k3s/k3s.yaml"

    # 检查是否存在且可执行
    if [ ! -f "/etc/rancher/k3s/k3s.yaml" ]; then
        echo -e "\033[31m[Error] k3s.yaml 文件不存在，请先安装 k3s\033[0m"
        return 1
    fi

    # 检查是否需要添加配置
    if ! grep -Fxq "$kubeconfig_line" "$bashrc_file"; then
        echo "$kubeconfig_line" | sudo tee -a "$bashrc_file" >/dev/null
        echo -e "\033[32m[Success] KUBECONFIG 已写入 $bashrc_file\033[0m"
    else
        echo -e "[Info] KUBECONFIG 已存在，无需修改"
    fi

    # 直接为当前 Shell 设置环境变量（临时生效）
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
    echo -e "\033[33m[Tips] 当前会话已临时生效，永久生效需重新登录或执行：source $bashrc_file\033[0m"
}

function check_k3s_status() {

    local STATUS=$(systemctl is-active k3s)

    if [ "$STATUS" = "active" ]; then
        echo -e "[Info] k3s 服务当前处于运行状态(active)。"
    else
        echo -e "[Info] k3s 服务当前不是运行状态(active)，它的状态是: $STATUS。尝试启动服务..."
        # 尝试启动k3s服务
        systemctl start k3s.service

        # 再次检查服务状态
        STATUS=$(systemctl is-active k3s.service)
        if [ "$STATUS" = "active" ]; then
            echo -e "[Info] k3s 服务已成功启动并正在运行。"
        else
            echo -e "\033[31m[Error] 无法启动 k3s 服务，请检查日志或配置\033。"
        fi
    fi
}

function apply_traefik_config {
    local config_file="../../chart_ssl/traefik-config.yml"

    # 检查配置文件是否存在
    if [[ ! -f "$config_file" ]]; then
        echo -e "\033[31m[Error] Traefik 配置文件未找到：$config_file\033[0m"
        return 1
    fi

    # 检查 kubectl 是否已安装
    if ! command -v kubectl &> /dev/null; then
        echo -e "\033[31m[Error] kubectl 未安装，请先安装 kubectl\033[0m"
        return 1
    fi

    # 检查 Kubernetes 集群是否可用
    if ! kubectl cluster-info &> /dev/null; then
        echo -e "\033[31m[Error] Kubernetes 集群不可用，请检查集群状态\033[0m"
        return 1
    fi

    # 执行 kubectl apply
    echo -e "[Info] 正在应用 Traefik 配置文件：$config_file"
    if kubectl apply -f "$config_file"; then
        echo -e "\033[32m[Success] Traefik 配置文件应用成功\033[0m"
        return 0
    else
        echo -e "\033[31m[Error] Traefik 配置文件应用失败\033[0m"
        return 1
    fi
}

function main {
    
    check_user
    check_arch || exit 1
    install_basic_tools

    local use_mirror=""
    [[ $1 == "cn" ]] && use_mirror="cn"

    # 安装K3s（如果尚未安装）
    if ! command -v k3s &> /dev/null; then
        install_k3s "$use_mirror" || exit 1
    else
        echo -e "[Info] K3s 已经安装，跳过安装步骤"
    fi

    # 安装Helm（如果尚未安装）
    if ! command -v helm &> /dev/null; then
        install_helm "$use_mirror" || exit 1
    else
        echo -e "[Info] Helm 已经安装，跳过安装步骤"
    fi
    check_k3s_status
    set_kubeconfig
    apply_traefik_config

    echo -e "\n\033[32m=== 全部工具安装完成 ===\033[0m"
    echo -e "K3s 版本：$(k3s --version | head -n1)"
    echo -e "Helm 版本：$(helm version --short)"
}

# 执行主函数，允许传递一个可选参数（cn）
main "$@"
