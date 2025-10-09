#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # 恢复默认颜色

# 默认配置
DEFAULT_VERSION="0.9.5"
IMAGE_BASE_DIR="/home/eulercopilot/images"

# 显示帮助信息
show_help() {
    echo -e "${YELLOW}使用说明:${NC}"
    echo -e "  $0 [选项] [参数]"
    echo -e "${YELLOW}选项:${NC}"
    echo -e "  -v, --version <版本>\t指定镜像版本 (默认: ${DEFAULT_VERSION})"
    echo -e "  -i, --import <文件>\t导入单个镜像文件"
    echo -e "  -d, --delete <镜像>\t删除指定镜像 (格式: repo/image:tag)"
    echo -e "  --delete-all\t\t删除所有neocopilot镜像"
    echo -e "  -h, --help\t\t显示帮助信息"
    echo -e "${YELLOW}示例:${NC}"
    echo -e "  $0 -v 0.9.4\t\t导入0.9.4版本的镜像"
    echo -e "  $0 -i $IMAGE_BASE_DIR/$DEFAULT_VERSION/myimage.tar\t导入单个镜像文件"
    echo -e "  $0 -d hub.oepkgs.net/neocopilot/authhub:0.9.3-arm\t删除指定镜像"
    echo -e "  $0 --delete-all\t删除所有neocopilot镜像"
    exit 0
}

# 参数解析
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -v|--version)
                eulercopilot_version="$2"
                shift 2
                ;;
            -i|--import)
                single_image_file="$2"
                shift 2
                ;;
            -d|--delete)
                image_to_delete="$2"
                shift 2
                ;;
            --delete-all)
                delete_all_images=true
                shift
                ;;
            -h|--help)
                show_help
                ;;
            *)
                echo -e "${RED}未知参数: $1${NC}"
                show_help
                exit 1
                ;;
        esac
    done
}

# 系统架构检测
detect_architecture() {
    ARCH=$(uname -m)
    case $ARCH in
        x86_64)
            ARCH_SUFFIX="x86"
            ;;
        aarch64|armv*)
            ARCH_SUFFIX="arm"
            ;;
        *)
            echo -e "${RED}不支持的架构: $ARCH${NC}"
            exit 1
            ;;
    esac
}

# 删除指定镜像
delete_image() {
    local image=$1
    echo -e "${YELLOW}正在删除镜像: $image${NC}"
    if sudo k3s ctr -n=k8s.io images rm "$image"; then
        echo -e "${GREEN} 删除成功${NC}"
    else
        echo -e "${RED} 删除失败${NC}"
    fi
}

# 删除所有neocopilot镜像
delete_all_neocopilot_images() {
    echo -e "${YELLOW}正在删除所有neocopilot镜像...${NC}"
    sudo k3s crictl images | grep neocopilot | awk '{print $1":"$2}' | while read -r image; do
        delete_image "$image"
    done
}

# 导入单个镜像文件
import_single_image() {
    local file=$1
    echo -e "${CYAN}正在导入单个镜像: $file${NC}"
    
    if [[ ! -f "$file" ]]; then
        echo -e "${RED}错误: 文件不存在 $file${NC}"
        exit 1
    fi

    if sudo k3s ctr -n=k8s.io images import "$file"; then
        echo -e "${GREEN} 导入成功${NC}"
    else
        echo -e "${RED} 导入失败${NC}"
        exit 1
    fi
}

# 批量导入镜像
batch_import_images() {
    local version=$1
    local image_dir="$IMAGE_BASE_DIR/$version"
    
    if [[ ! -d "$image_dir" ]]; then
        echo -e "${RED}错误：镜像目录不存在 $image_dir${NC}"
        exit 1
    fi

    echo -e "${CYAN}正在扫描目录: $image_dir${NC}"
    echo -e "${CYAN}找到以下TAR文件：${NC}"
    ls -1 "$image_dir"/*.tar

    local success_count=0
    local fail_count=0

    for tar_file in "$image_dir"/*.tar; do
        [[ -f "$tar_file" ]] || continue

        echo -e "\n${BLUE}正在导入 $tar_file...${NC}"

        if sudo k3s ctr -n=k8s.io images import "$tar_file"; then
            ((success_count++))
            echo -e "${GREEN} 导入成功${NC}"
        else
            ((fail_count++))
            echo -e "${RED} 导入失败${NC}"
        fi
    done

    echo -e "\n${CYAN}导入结果：${NC}"
    echo -e "${GREEN}成功: $success_count 个${NC}"
    echo -e "${RED}失败: $fail_count 个${NC}"
    
    return $fail_count
}

# 镜像完整性检查
check_images() {
    local version=$1
    local missing_count=0

    # 基础镜像列表（使用版本变量）
    local base_images=(
        "hub.oepkgs.net/neocopilot/euler-copilot-framework:${version}-arm"
        "hub.oepkgs.net/neocopilot/euler-copilot-web:${version}-arm"
        "hub.oepkgs.net/neocopilot/data_chain_back_end:${version}-arm"
        "hub.oepkgs.net/neocopilot/data_chain_web:${version}-arm"
        "hub.oepkgs.net/neocopilot/authhub:0.9.3-arm"
        "hub.oepkgs.net/neocopilot/authhub-web:0.9.3-arm"
        "hub.oepkgs.net/neocopilot/opengauss:latest-arm"
        "hub.oepkgs.net/neocopilot/redis:7.4-alpine-arm"
        "hub.oepkgs.net/neocopilot/mysql:8-arm"
        "hub.oepkgs.net/neocopilot/minio:empty-arm"
        "hub.oepkgs.net/neocopilot/mongo:7.0.16-arm"
        "hub.oepkgs.net/neocopilot/secret_inject:dev-arm"
    )

    # 根据架构调整预期镜像标签
    local expected_images=()
    for image in "${base_images[@]}"; do
        if [[ "$ARCH_SUFFIX" == "x86" ]]; then
            expected_image="${image/-arm/-x86}"
        else
            expected_image="$image"
        fi
        expected_images+=("$expected_image")
    done

    echo -e "\n${MAGENTA}开始镜像完整性检查：${NC}"
    for image in "${expected_images[@]}"; do
        if sudo k3s ctr -n=k8s.io images ls | grep -q "$image"; then
            echo -e "${GREEN}[存在] $image${NC}"
        else
            echo -e "${RED}[缺失] $image${NC}"
            ((missing_count++))
        fi
    done

    echo -e "\n${MAGENTA}使用crictl检查镜像：${NC}"
    sudo k3s crictl images | grep neocopilot

    if [[ $missing_count -gt 0 ]]; then
        echo -e "\n${RED}警告：缺少 $missing_count 个必需镜像${NC}"
        return 1
    else
        echo -e "\n${GREEN}所有必需镜像已就绪${NC}"
        return 0
    fi
}

# 主函数
main() {
    parse_args "$@"
    detect_architecture

    # 处理删除操作
    if [[ -n "$image_to_delete" ]]; then
        delete_image "$image_to_delete"
        exit 0
    fi

    if [[ "$delete_all_images" == true ]]; then
        delete_all_neocopilot_images
        exit 0
    fi

    # 处理单个镜像导入
    if [[ -n "$single_image_file" ]]; then
        import_single_image "$single_image_file"
        exit 0
    fi

    # 默认批量导入模式
    local version=${eulercopilot_version:-$DEFAULT_VERSION}
    
    echo -e "${YELLOW}==============================${NC}"
    echo -e "${CYAN}架构检测\t: ${ARCH_SUFFIX}${NC}"
    echo -e "${CYAN}目标版本\t: ${version}${NC}"
    echo -e "${CYAN}镜像目录\t: ${IMAGE_BASE_DIR}/${version}${NC}"
    echo -e "${YELLOW}==============================${NC}"

    batch_import_images "$version"
    import_result=$?

    if [[ $import_result -eq 0 ]]; then
        check_images "$version" || exit 1
    else
        echo -e "${RED}存在导入失败的镜像，跳过完整性检查${NC}"
        exit 1
    fi

    echo -e "${GREEN}系统准备就绪，所有镜像可用${NC}"
}

# 执行主函数
main "$@"
exit 0
