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

# Function: Display help information
function help {
    echo -e "Usage: bash install_tools.sh [options]"
    echo -e "Options:"
    echo -e "  --mirror cn          Use China mirror for acceleration"
    echo -e "  --k3s-version VERSION  Specify k3s version (default: v1.30.2+k3s1)"
    echo -e "  --helm-version VERSION Specify helm version (default: v3.15.0)"
    echo -e "  -h, --help           Show help information"
    echo -e "Examples:"
    echo -e "  bash install_tools.sh                        # Install with default settings"
    echo -e "  bash install_tools.sh --mirror cn            # Use China mirror"
    echo -e "  bash install_tools.sh --k3s-version v1.30.1+k3s1 --helm-version v3.15.0"
    echo -e "Offline installation instructions:"
    echo -e "1. Rename k3s binary to k3s or k3s-arm64 and place in $TOOLS_DIR"
    echo -e "2. Rename k3s image package to k3s-airgap-images-<arch>.tar.zst and place in $TOOLS_DIR"
    echo -e "3. Rename helm package to helm-<version>-linux-<arch>.tar.gz and place in $TOOLS_DIR"
}

# Parse command line arguments
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
            echo "Unknown parameter: $1"
            help
            exit 1
            ;;
    esac
done

# Enhanced network check
function check_network {
    echo -e "[Info] Checking network connection..."
    if curl --retry 3 --retry-delay 2 --connect-timeout 5 -Is https://github.com | head -n 1 | grep 200 >/dev/null; then
        echo -e "\033[32m[OK] Network connection normal\033[0m"
        return 0
    else
        echo -e "\033[33m[Warn] No network connection, switching to offline mode\033[0m"
        return 1
    fi
}

function check_user {
    if [[ $(id -u) -ne 0 ]]; then
        echo -e "\033[31m[Error] Please run this script with root privileges!\033[0m"
        exit 1
    fi
}

function check_arch {
    case $ARCH in
        x86_64)  ARCH=amd64 ;;
        aarch64) ARCH=arm64 ;;
        *)
            echo -e "\033[31m[Error] Current CPU architecture not supported\033[0m"
            return 1
            ;;
    esac
    return 0
}

install_basic_tools() {
    # Install basic tools
    echo "Installing tar, vim, curl, wget..."
    yum install -y tar vim curl wget python3

    # Check if pip is installed
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

    # Auto-complete v prefix
    if [[ $k3s_version != v* ]]; then
        k3s_version="v$k3s_version"
    fi

    local image_name="k3s-airgap-images-$ARCH.tar.zst"
    local bin_name="k3s"
    [[ $ARCH == "arm64" ]] && bin_name="k3s-arm64"

    # Check if local files exist
    if [[ -f "$TOOLS_DIR/$bin_name" && -f "$TOOLS_DIR/$image_name" ]]; then
        echo -e "\033[32m[Info] Local K3s installation files detected, using local files\033[0m"
        return 0
    else
        echo -e "\033[33m[Info] Local K3s installation files incomplete, attempting online download\033[0m"
        return 1
    fi
}

function install_k3s {
    local version="${1:-v1.30.2+k3s1}"
    local use_mirror="$2"

    # Auto-complete v prefix
    if [[ $version != v* ]]; then
        version="v$version"
    fi
    local k3s_version="$version"

    local image_name="k3s-airgap-images-$ARCH.tar.zst"
    local bin_name="k3s"
    [[ $ARCH == "arm64" ]] && bin_name="k3s-arm64"

    # First check if local files exist
    if check_local_k3s_files "$version"; then
        # Use local files for installation
        echo -e "\033[33m[Info] Entering offline K3s installation mode\033[0m"

        echo -e "[Info] Installing using local packages..."
        cp "$TOOLS_DIR/$bin_name" /usr/local/bin/k3s
        chmod +x /usr/local/bin/k3s

        mkdir -p /var/lib/rancher/k3s/agent/images
        cp "$TOOLS_DIR/$image_name" "/var/lib/rancher/k3s/agent/images/$image_name"

        # Offline installation script
        local local_install_script="$TOOLS_DIR/k3s-install.sh"
        if [[ -f "$local_install_script" ]]; then
            echo -e "\033[33m[Info] Using local installation script: $local_install_script\033[0m"
            chmod +x "$local_install_script"
            if INSTALL_K3S_SKIP_DOWNLOAD=true "$local_install_script"; then
                echo -e "\033[32m[Success] K3s installation completed\033[0m"
                return 0
            else
                echo -e "\033[31m[Error] Local installation failed\033[0m"
                return 1
            fi
        else
            echo -e "\033[31m[Error] Missing local installation script: $local_install_script\033[0m"
            echo -e "Please pre-download and save to specified directory:"
            echo -e "Online: curl -sfL https://get.k3s.io -o $local_install_script"
            echo -e "China mirror: curl -sfL https://rancher-mirror.rancher.cn/k3s/k3s-install.sh -o $local_install_script"
            return 1
        fi
    else
        # Local files not found, check network
        if check_network; then
            echo -e "\033[32m[Info] Starting online K3s installation\033[0m"

            # Online download and installation
            local k3s_bin_url="$GITHUB_MIRROR/https://github.com/k3s-io/k3s/releases/download/$k3s_version/$bin_name"
            local k3s_image_url="$GITHUB_MIRROR/https://github.com/k3s-io/k3s/releases/download/$k3s_version/$image_name"

            echo -e "[Info] Downloading K3s binary..."
            if ! curl -L "$k3s_bin_url" -o /usr/local/bin/k3s; then
                echo -e "\033[31m[Error] Binary download failed\033[0m"
                return 1
            fi
            chmod +x /usr/local/bin/k3s

            echo -e "[Info] Downloading dependency images..."
            mkdir -p /var/lib/rancher/k3s/agent/images
            if ! curl -L "$k3s_image_url" -o "/var/lib/rancher/k3s/agent/images/$image_name"; then
                echo -e "\033[33m[Warn] Image download failed, may affect offline capability\033[0m"
            fi

            local install_source="https://get.k3s.io"
            [[ $use_mirror == "cn" ]] && install_source="https://rancher-mirror.rancher.cn/k3s/k3s-install.sh"

            echo -e "\033[32m[Info] Using online installation script\033[0m"
            if ! curl -sfL "$install_source" | INSTALL_K3S_SKIP_DOWNLOAD=true sh -; then
                echo -e "\033[31m[Error] Online installation failed\033[0m"
                return 1
            fi
        else
            # Neither local files nor network connection available
            echo -e "\033[31m[Error] Cannot install K3s:\033[0m"
            echo -e "1. Missing necessary local installation files"
            echo -e "2. Network unavailable, cannot download installation files"
            echo -e "Please perform one of the following:"
            echo -e "- Ensure network connection and retry"
            echo -e "- Or pre-place the following files in $TOOLS_DIR directory:"
            echo -e "  - $bin_name"
            echo -e "  - $image_name"
            echo -e "  - k3s-install.sh (optional)"
            return 1
        fi
    fi
}

function check_local_helm_file {
    local version="${1:-v3.15.0}"
    local helm_version="$version"

    # Auto-complete v prefix
    if [[ $helm_version != v* ]]; then
        helm_version="v$helm_version"
    fi

    local file_name="helm-${helm_version}-linux-${ARCH}.tar.gz"

    # Check if local file exists
    if [[ -f "$TOOLS_DIR/$file_name" ]]; then
        echo -e "\033[32m[Info] Local Helm installation file detected, using local file\033[0m"
        return 0
    else
        echo -e "\033[33m[Info] Local Helm installation file not found, attempting online download\033[0m"
        return 1
    fi
}

function install_helm {
    local version="${1:-v3.15.0}"
    local use_mirror="$2"

    # Auto-complete v prefix
    if [[ $version != v* ]]; then
        version="v$version"
    fi
    local helm_version="$version"

    local file_name="helm-${helm_version}-linux-${ARCH}.tar.gz"

    # First check if local file exists
    if check_local_helm_file "$version"; then
        echo -e "\033[33m[Info] Entering offline Helm installation mode\033[0m"
        echo -e "[Info] Installing using local package..."
        cp "$TOOLS_DIR/$file_name" .
    else
        # Local file not found, check network
        if check_network; then
            echo -e "\033[32m[Info] Starting online Helm installation\033[0m"

            local base_url="https://get.helm.sh"
            if [[ $use_mirror == "cn" ]]; then
                local helm_version_without_v="${helm_version#v}"
                base_url="https://kubernetes.oss-cn-hangzhou.aliyuncs.com/charts/helm/${helm_version_without_v}"
            fi

            echo -e "[Info] Downloading Helm..."
            if ! curl -L "$base_url/$file_name" -o "$file_name"; then
                echo -e "\033[31m[Error] Download failed\033[0m"
                return 1
            fi
        else
            # Neither local file nor network connection available
            echo -e "\033[31m[Error] Cannot install Helm:\033[0m"
            echo -e "1. Missing necessary local installation file"
            echo -e "2. Network unavailable, cannot download installation file"
            echo -e "Please perform one of the following:"
            echo -e "- Ensure network connection and retry"
            echo -e "- Or pre-place the following file in $TOOLS_DIR directory:"
            echo -e "  - $file_name"
            return 1
        fi
    fi

    echo -e "[Info] Extracting and installing..."
    tar -zxvf "$file_name" --strip-components 1 -C /usr/local/bin "linux-$ARCH/helm"
    chmod +x /usr/local/bin/helm
    rm -f "$file_name"

    echo -e "\033[32m[Success] Helm installation completed\033[0m"
    return 0
}

function check_k3s_status() {
    local STATUS=$(systemctl is-active k3s)

    if [ "$STATUS" = "active" ]; then
        echo -e "[Info] k3s service is currently active."
    else
        echo -e "[Info] k3s service is not active, current status: $STATUS. Attempting to start service..."
        # Try to start k3s service
        systemctl start k3s.service

        # Check service status again
        STATUS=$(systemctl is-active k3s.service)
        if [ "$STATUS" = "active" ]; then
            echo -e "[Info] k3s service successfully started and running."
        else
            echo -e "\033[31m[Error] Unable to start k3s service, please check logs or configuration\033[0m"
        fi
    fi
}

function main {
    # Create tools directory
    mkdir -p "$TOOLS_DIR"

    check_user
    check_arch || exit 1
    install_basic_tools

    local use_mirror="$MIRROR"
    local k3s_version="${K3S_VERSION:-v1.30.2+k3s1}"
    local helm_version="${HELM_VERSION:-v3.15.0}"

    # Install K3s (if not already installed)
    if ! command -v k3s &> /dev/null; then
        install_k3s "$k3s_version" "$use_mirror" || exit 1
    else
        echo -e "[Info] K3s already installed, skipping installation"
    fi
     # Check network first
    if check_network; then
        echo -e "\033[32m[Info] Online environment, skipping image import\033[0m"
    else
        echo -e "\033[33m[Info] Offline environment, starting local image import, ensure all image files exist in local directory\033[0m"
        bash "$IMPORT_SCRIPT/9-other-script/import_images.sh" -v "$eulercopilot_version"
    fi

    # Install Helm (if not already installed)
    if ! command -v helm &> /dev/null; then
        install_helm "$helm_version" "$use_mirror" || exit 1
    else
        echo -e "[Info] Helm already installed, skipping installation"
    fi
    mkdir -p ~/.kube
    ln -sf /etc/rancher/k3s/k3s.yaml ~/.kube/config
    check_k3s_status

    echo -e "\n\033[32m=== All tools installation completed ===\033[0m"
    echo -e "K3s version: $(k3s --version | head -n1)"
    echo -e "Helm version: $(helm version --short)"
}

# Execute main function
main
