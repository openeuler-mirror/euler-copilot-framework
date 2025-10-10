#!/bin/bash

GITHUB_MIRROR="https://gh-proxy.com"
ARCH=$(uname -m)
TOOLS_DIR="/home/eulercopilot/tools"
eulercopilot_version=0.10.0

SCRIPT_PATH="$(
  cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1
  pwd
)/$(basename "${BASH_SOURCE[0]}")"

IMPORT_SCRIPT="$(
  canonical_path=$(readlink -f "$SCRIPT_PATH" 2>/dev/null || echo "$SCRIPT_PATH")
  dirname "$(dirname "$canonical_path")"
)"


# 函数：显示帮助信息
function help {
    echo -e "用法：bash install_tools.sh [选项]"
    echo -e "选项："
    echo -e "  --mirror cn          使用国内镜像加速"
    echo -e "  --k3s-version VERSION  指定k3s版本（默认：v1.30.2+k3s1）"
    echo -e "  --helm-version VERSION 指定helm版本（默认：v3.15.0）"
    echo -e "  -h, --help           显示帮助信息"
    echo -e "示例："
    echo -e "  bash install_tools.sh                        # 使用默认设置安装"
    echo -e "  bash install_tools.sh --mirror cn            # 使用国内镜像"
    echo -e "  bash install_tools.sh --k3s-version v1.30.1+k3s1 --helm-version v3.15.0"
    echo -e "离线安装说明："
    echo -e "1. 将k3s二进制文件重命名为 k3s 或 k3s-arm64 并放在 $TOOLS_DIR"
    echo -e "2. 将k3s镜像包重命名为 k3s-airgap-images-<架构>.tar.zst 放在 $TOOLS_DIR"
    echo -e "3. 将helm包重命名为 helm-<版本>-linux-<架构>.tar.gz 放在 $TOOLS_DIR"
}

# 解析命令行参数
MIRROR=""
K3S_VERSION=""
HELM_VERSION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mirror)
            MIRROR="$2"
            shift 2
            ;;
        --k3s-version)
            K3S_VERSION="$2"
            shift 2
            ;;
        --helm-version)
            HELM_VERSION="$2"
            shift 2
            ;;
        cn)
            MIRROR="cn"
            shift
            ;;
        -h|--help)
            help
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            help
            exit 1
            ;;
    esac
done

# 增强型网络检查
function check_network {
    echo -e "[Info] 正在检查网络连接..."
    if curl --retry 3 --retry-delay 2 --connect-timeout 5 -Is https://github.com | head -n 1 | grep 200 >/dev/null; then
        echo -e "\033[32m[OK] 网络连接正常\033[0m"
        return 0
    else
        echo -e "\033[33m[Warn] 无网络连接，切换到离线模式\033[0m"
        return 1
    fi
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
    yum install -y tar vim curl wget python3

    # 检查 pip 是否已安装
    if ! command -v pip3 &> /dev/null; then
        echo -e "pip could not be found, installing python3-pip..."
        yum install -y python3-pip
    else
        echo -e "pip is already installed."
    fi

    echo "Installing requests ruamel.yaml with pip3..."
    if ! pip3 install \
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

function check_local_k3s_files {
    local version="${1:-v1.30.2+k3s1}"
    local k3s_version="$version"
    
    # 自动补全v前缀
    if [[ $k3s_version != v* ]]; then
        k3s_version="v$k3s_version"
    fi

    local image_name="k3s-airgap-images-$ARCH.tar.zst"
    local bin_name="k3s"
    [[ $ARCH == "arm64" ]] && bin_name="k3s-arm64"

    # 检查本地文件是否存在
    if [[ -f "$TOOLS_DIR/$bin_name" && -f "$TOOLS_DIR/$image_name" ]]; then
        echo -e "\033[32m[Info] 检测到本地K3s安装文件，将使用本地文件安装\033[0m"
        return 0
    else
        echo -e "\033[33m[Info] 本地K3s安装文件不完整，将尝试在线下载\033[0m"
        return 1
    fi
}

function install_k3s {
    local version="${1:-v1.30.2+k3s1}"
    local use_mirror="$2"

    # 自动补全v前缀
    if [[ $version != v* ]]; then
        version="v$version"
    fi
    local k3s_version="$version"

    local image_name="k3s-airgap-images-$ARCH.tar.zst"
    local bin_name="k3s"
    [[ $ARCH == "arm64" ]] && bin_name="k3s-arm64"

    # 首先检查本地文件是否存在
    if check_local_k3s_files "$version"; then
        # 使用本地文件安装
        echo -e "\033[33m[Info] 进入离线安装K3s模式\033[0m"

        echo -e "[Info] 使用本地包安装..."
        cp "$TOOLS_DIR/$bin_name" /usr/local/bin/k3s
        chmod +x /usr/local/bin/k3s

        mkdir -p /var/lib/rancher/k3s/agent/images
        cp "$TOOLS_DIR/$image_name" "/var/lib/rancher/k3s/agent/images/$image_name"

        # 离线安装脚本
        local local_install_script="$TOOLS_DIR/k3s-install.sh"
        if [[ -f "$local_install_script" ]]; then
            echo -e "\033[33m[Info] 使用本地安装脚本：$local_install_script\033[0m"
            chmod +x "$local_install_script"
            if INSTALL_K3S_SKIP_DOWNLOAD=true "$local_install_script"; then
                echo -e "\033[32m[Success] K3s安装完成\033[0m"
                return 0
            else
                echo -e "\033[31m[Error] 本地安装失败\033[0m"
                return 1
            fi
        else
            echo -e "\033[31m[Error] 缺少本地安装脚本：$local_install_script\033[0m"
            echo -e "请预先下载并保存到指定目录："
            echo -e "在线模式：curl -sfL https://get.k3s.io -o $local_install_script"
            echo -e "国内镜像：curl -sfL https://rancher-mirror.rancher.cn/k3s/k3s-install.sh -o $local_install_script"
            return 1
        fi
    else
        # 本地文件不存在，检查网络
        if check_network; then
            echo -e "\033[32m[Info] 开始在线安装K3s\033[0m"

            # 在线下载安装
            local k3s_bin_url="$GITHUB_MIRROR/https://github.com/k3s-io/k3s/releases/download/$k3s_version/$bin_name"
            local k3s_image_url="$GITHUB_MIRROR/https://github.com/k3s-io/k3s/releases/download/$k3s_version/$image_name"

            echo -e "[Info] 下载K3s二进制文件..."
            if ! curl -L "$k3s_bin_url" -o /usr/local/bin/k3s; then
                echo -e "\033[31m[Error] 二进制文件下载失败\033[0m"
                return 1
            fi
            chmod +x /usr/local/bin/k3s

            echo -e "[Info] 下载依赖镜像..."
            mkdir -p /var/lib/rancher/k3s/agent/images
            if ! curl -L "$k3s_image_url" -o "/var/lib/rancher/k3s/agent/images/$image_name"; then
                echo -e "\033[33m[Warn] 镜像下载失败，可能影响离线能力\033[0m"
            fi

            local install_source="https://get.k3s.io"
            [[ $use_mirror == "cn" ]] && install_source="https://rancher-mirror.rancher.cn/k3s/k3s-install.sh"

            echo -e "\033[32m[Info] 使用在线安装脚本\033[0m"
            if ! curl -sfL "$install_source" | INSTALL_K3S_SKIP_DOWNLOAD=true sh -; then
                echo -e "\033[31m[Error] 在线安装失败\033[0m"
                return 1
            fi
        else
            # 既没有本地文件，也没有网络连接
            echo -e "\033[31m[Error] 无法安装K3s：\033[0m"
            echo -e "1. 本地缺少必要的安装文件"
            echo -e "2. 网络不可用，无法下载安装文件"
            echo -e "请执行以下操作之一："
            echo -e "- 确保网络连接正常后重试"
            echo -e "- 或预先将以下文件放置在 $TOOLS_DIR 目录："
            echo -e "  - $bin_name"
            echo -e "  - $image_name"
            echo -e "  - k3s-install.sh (可选)"
            return 1
        fi
    fi
}

function check_local_helm_file {
    local version="${1:-v3.15.0}"
    local helm_version="$version"
    
    # 自动补全v前缀
    if [[ $helm_version != v* ]]; then
        helm_version="v$helm_version"
    fi

    local file_name="helm-${helm_version}-linux-${ARCH}.tar.gz"

    # 检查本地文件是否存在
    if [[ -f "$TOOLS_DIR/$file_name" ]]; then
        echo -e "\033[32m[Info] 检测到本地Helm安装文件，将使用本地文件安装\033[0m"
        return 0
    else
        echo -e "\033[33m[Info] 本地Helm安装文件不存在，将尝试在线下载\033[0m"
        return 1
    fi
}

function install_helm {
    local version="${1:-v3.15.0}"
    local use_mirror="$2"

    # 自动补全v前缀
    if [[ $version != v* ]]; then
        version="v$version"
    fi
    local helm_version="$version"

    local file_name="helm-${helm_version}-linux-${ARCH}.tar.gz"

    # 首先检查本地文件是否存在
    if check_local_helm_file "$version"; then
        echo -e "\033[33m[Info] 进入离线安装Helm模式\033[0m"
        echo -e "[Info] 使用本地包安装..."
        cp "$TOOLS_DIR/$file_name" .
    else
        # 本地文件不存在，检查网络
        if check_network; then
            echo -e "\033[32m[Info] 开始在线安装Helm\033[0m"

            local base_url="https://get.helm.sh"
            if [[ $use_mirror == "cn" ]]; then
                local helm_version_without_v="${helm_version#v}"
                base_url="https://kubernetes.oss-cn-hangzhou.aliyuncs.com/charts/helm/${helm_version_without_v}"
            fi

            echo -e "[Info] 下载Helm..."
            if ! curl -L "$base_url/$file_name" -o "$file_name"; then
                echo -e "\033[31m[Error] 下载失败\033[0m"
                return 1
            fi
        else
            # 既没有本地文件，也没有网络连接
            echo -e "\033[31m[Error] 无法安装Helm：\033[0m"
            echo -e "1. 本地缺少必要的安装文件"
            echo -e "2. 网络不可用，无法下载安装文件"
            echo -e "请执行以下操作之一："
            echo -e "- 确保网络连接正常后重试"
            echo -e "- 或预先将以下文件放置在 $TOOLS_DIR 目录："
            echo -e "  - $file_name"
            return 1
        fi
    fi

    echo -e "[Info] 解压安装..."
    tar -zxvf "$file_name" --strip-components 1 -C /usr/local/bin "linux-$ARCH/helm"
    chmod +x /usr/local/bin/helm
    rm -f "$file_name"

    echo -e "\033[32m[Success] Helm安装完成\033[0m"
    return 0
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
            echo -e "\033[31m[Error] 无法启动 k3s 服务，请检查日志或配置\033[0m"
        fi
    fi
}

function main {
    # 创建工具目录
    mkdir -p "$TOOLS_DIR"

    check_user
    check_arch || exit 1
    install_basic_tools

    local use_mirror="$MIRROR"
    local k3s_version="${K3S_VERSION:-v1.30.2+k3s1}"
    local helm_version="${HELM_VERSION:-v3.15.0}"

    # 安装K3s（如果尚未安装）
    if ! command -v k3s &> /dev/null; then
        install_k3s "$k3s_version" "$use_mirror" || exit 1
    else
        echo -e "[Info] K3s 已经安装，跳过安装步骤"
    fi
     # 优先检查网络
    if check_network; then
        echo -e "\033[32m[Info] 在线环境，跳过镜像导入\033[0m"
    else
        echo -e "\033[33m[Info] 离线环境，开始导入本地镜像，请确保本地目录已存在所有镜像文件\033[0m"
        bash "$IMPORT_SCRIPT/9-other-script/import_images.sh" -v "$eulercopilot_version"
    fi

    # 安装Helm（如果尚未安装）
    if ! command -v helm &> /dev/null; then
        install_helm "$helm_version" "$use_mirror" || exit 1
    else
        echo -e "[Info] Helm 已经安装，跳过安装步骤"
    fi
    mkdir -p ~/.kube
    ln -sf /etc/rancher/k3s/k3s.yaml ~/.kube/config
    check_k3s_status

    echo -e "\n\033[32m=== 全部工具安装完成 ===\033[0m"
    echo -e "K3s 版本：$(k3s --version | head -n1)"
    echo -e "Helm 版本：$(helm version --short)"
}

# 执行主函数
main
