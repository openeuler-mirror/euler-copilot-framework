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
        echo -e "pip could not be found, installing python3-pip..."
        yum install -y python3-pip
    else
        echo -e "pip is already installed."
    fi
 
    echo "Installing requests ruamel.yaml with pip..."
    if ! pip install \
        --disable-pip-version-check \
        --retries 3 \
        --timeout 60 \
        --trusted-host mirrors.huaweicloud.com \
        -i https://mirrors.huaweicloud.com/repository/pypi/simple \
        ruamel.yaml requests; then
        echo -e "[ERROR] Failed to install ruamel.yaml and requests via pip" >&2
    fi
    echo "All basic tools have been installed."
    return 0
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
    local k3s_config="/etc/rancher/k3s/k3s.yaml"
    local bashrc_file="$HOME/.bashrc"
    local kubeconfig_line="export KUBECONFIG=$k3s_config"

    # 检查 k3s.yaml 是否存在
    if [ ! -f "$k3s_config" ]; then
        echo -e "\033[31m[Error] k3s.yaml 文件不存在，请先安装 k3s 或检查路径：$k3s_config\033[0m"
        return 1
    fi

    # 检查文件权限（至少需要可读权限）
    if [ ! -r "$k3s_config" ]; then
        echo -e "\033[33m[Warn] k3s.yaml 文件不可读，尝试修复权限...\033[0m"
        sudo chmod 644 "$k3s_config" || {
            echo -e "\033[31m[Error] 权限修复失败，请手动执行：sudo chmod 644 $k3s_config\033[0m"
            return 1
        }
    fi

    # 检查并更新 .bashrc（兼容 root 和普通用户）
    if ! grep -Fxq "$kubeconfig_line" "$bashrc_file"; then
        echo "$kubeconfig_line" | tee -a "$bashrc_file" >/dev/null
        echo -e "\033[32m[Success] KUBECONFIG 已写入 $bashrc_file\033[0m"
    else
        echo -e "\033[34m[Info] KUBECONFIG 已存在，无需修改\033[0m"
    fi

    # 设置当前 Shell 环境变量
    export KUBECONFIG="$k3s_config"
    echo -e "\033[33m[Tips] 当前会话已临时生效，永久生效需重新登录或执行：source $bashrc_file\033[0m"

    # 验证集群连通性
    if ! kubectl cluster-info &>/dev/null; then
        echo -e "\033[31m[Critical] 集群连接失败，可能原因：\033[0m"
        echo -e "1. Kubernetes 未运行 → 执行: sudo systemctl status k3s"
        echo -e "2. API 地址配置错误 → 检查 $k3s_config 中的 server 字段"
        echo -e "3. 防火墙阻止连接 → 检查端口 6443 是否开放"
        return 1
    fi
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
    # 获取脚本绝对路径
    local script_dir
    script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    echo $script_dir 
    # 构造配置文件绝对路径
    local config_file="${script_dir}/../../chart_ssl/traefik-config.yml"

    # 带颜色的输出函数
    local RED='\033[31m'
    local GREEN='\033[32m'
    local YELLOW='\033[33m'
    local RESET='\033[0m'

    # 打印调试信息
    echo -e "${YELLOW}[Debug] 当前脚本目录：${script_dir}${RESET}"
    echo -e "${YELLOW}[Debug] 配置文件路径：${config_file}${RESET}"

    # 检查配置文件是否存在
    if [[ ! -f "$config_file" ]]; then
        echo -e "${RED}[Error] Traefik 配置文件未找到：${config_file}${RESET}" >&2
        echo -e "${YELLOW}建议检查步骤：" >&2
        echo -e "1. 确认 chart_ssl 目录是否存在" >&2
        echo -e "2. 确认文件权限（需至少可读权限）" >&2
        echo -e "3. 检查文件路径是否正确${RESET}" >&2
        return 1
    fi

    # 检查 kubectl 是否已安装
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}[Error] kubectl 未安装，请先安装 kubectl${RESET}" >&2
        echo -e "${YELLOW}安装建议：https://kubernetes.io/docs/tasks/tools/${RESET}" >&2
        return 1
    fi

    # 检查 Kubernetes 集群是否可用
    if ! kubectl cluster-info &> /dev/null; then
        echo -e "${RED}[Error] Kubernetes 集群不可用，请检查：${RESET}" >&2
        echo -e "${YELLOW}1. 集群是否正在运行" >&2
        echo -e "2. kubeconfig 配置是否正确" >&2
        echo -e "3. 网络连接是否正常${RESET}" >&2
        return 1
    fi

    # 执行 kubectl apply
    echo -e "[Info] 正在应用 Traefik 配置文件：$config_file"
    if kubectl apply -f "$config_file"; then
        echo -e "${GREEN}[Success] Traefik 配置文件应用成功${RESET}"
        
        # 添加验证步骤
        echo -e "\n[Info] 验证部署状态："
        kubectl get svc traefik -n kube-system
        kubectl get pods -n kube-system -l app.kubernetes.io/name=traefik
        
        return 0
    else
        echo -e "${RED}[Error] Traefik 配置文件应用失败${RESET}" >&2
        echo -e "${YELLOW}排障建议：" >&2
        echo -e "1. 检查 YAML 语法：kubectl apply --validate -f ${config_file}" >&2
        echo -e "2. 查看详细日志：kubectl logs -n kube-system -l app.kubernetes.io/name=traefik" >&2
        echo -e "3. 检查资源配置冲突${RESET}" >&2
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
