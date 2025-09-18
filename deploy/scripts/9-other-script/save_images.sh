#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 恢复默认颜色

# 默认配置
eulercopilot_version="0.10.0"
ARCH_SUFFIX=""
OUTPUT_DIR="/home/eulercopilot/images/${eulercopilot_version}"

# 显示帮助信息
show_help() {
    echo -e "${YELLOW}使用说明:${NC}"
    echo -e "  $0 [选项]"
    echo -e ""
    echo -e "${YELLOW}选项:${NC}"
    echo -e "  --help            显示此帮助信息"
    echo -e "  --version <版本>  指定 EulerCopilot 版本 (默认: ${eulercopilot_version})"
    echo -e "  --arch <架构>     指定系统架构 (arm/x86, 默认自动检测)"
    echo -e ""
    echo -e "${YELLOW}示例:${NC}"
    echo -e "  $0 --version ${eulercopilot_version} --arch arm"
    echo -e "  $0 --help"
    exit 0
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)
            show_help
            ;;
        --version)
            if [ -n "$2" ]; then
                eulercopilot_version="$2"
                OUTPUT_DIR="/home/eulercopilot/images/${eulercopilot_version}"
                shift
            else
                echo -e "${RED}错误: --version 需要指定一个版本号${NC}"
                exit 1
            fi
            ;;
        --arch)
            if [ -n "$2" ]; then
                case "$2" in
                    arm|x86)
                        ARCH_SUFFIX="$2"
                        ;;
                    *)
                        echo -e "${RED}错误: 不支持的架构 '$2'，必须是 arm 或 x86${NC}"
                        exit 1
                        ;;
                esac
                shift
            else
                echo -e "${RED}错误: --arch 需要指定一个架构 (arm/x86)${NC}"
                exit 1
            fi
            ;;
        *)
            echo -e "${RED}未知参数: $1${NC}"
            show_help
            ;;
    esac
    shift
done

# 自动检测架构（如果未通过参数指定）
if [ -z "$ARCH_SUFFIX" ]; then
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
fi

mkdir -p "$OUTPUT_DIR"

# 镜像列表（使用版本变量）
BASE_IMAGES=(
    "hub.oepkgs.net/neocopilot/euler-copilot-framework:${eulercopilot_version}-arm"
    "hub.oepkgs.net/neocopilot/euler-copilot-web:${eulercopilot_version}-arm"
    "hub.oepkgs.net/neocopilot/data_chain_back_end:${eulercopilot_version}-arm"
    "hub.oepkgs.net/neocopilot/data_chain_web:${eulercopilot_version}-arm"
    "hub.oepkgs.net/neocopilot/authhub:0.9.3-arm"
    "hub.oepkgs.net/neocopilot/authhub-web:0.9.3-arm"
    "hub.oepkgs.net/neocopilot/opengauss:latest-arm"
    "hub.oepkgs.net/neocopilot/redis:7.4-alpine-arm"
    "hub.oepkgs.net/neocopilot/mysql:8-arm"
    "hub.oepkgs.net/neocopilot/minio:empty-arm"
    "hub.oepkgs.net/neocopilot/mongo:7.0.16-arm"
    "hub.oepkgs.net/neocopilot/secret_inject:dev-arm"
)

# 预定义文件名列表（与BASE_IMAGES顺序严格对应）
FILE_NAMES=(
    "euler-copilot-framework.tar"
    "euler-copilot-web.tar"
    "data_chain_back_end.tar"
    "data_chain_web.tar"
    "authhub.tar"
    "authhub-web.tar"
    "opengauss.tar"
    "redis.tar"
    "mysql.tar"
    "minio.tar"
    "mongo.tar"
    "secret_inject.tar"
)

# 校验列表一致性
if [ ${#BASE_IMAGES[@]} -ne ${#FILE_NAMES[@]} ]; then
    echo -e "${RED}错误：镜像列表与文件名列表数量不匹配${NC}"
    exit 1
fi

# 初始化计数器
total=${#BASE_IMAGES[@]}
success=0
fail=0

# 镜像处理函数
process_image() {
    local raw_image=$1
    local filename=$2

    # 调整架构标签
    local adjusted_image="${raw_image/-arm/-${ARCH_SUFFIX}}"
    local output_path="${OUTPUT_DIR}/${filename}"

    echo -e "\n${BLUE}正在处理：${adjusted_image}${NC}"

    # 拉取镜像
    if ! docker pull "$adjusted_image"; then
        echo -e "${RED}拉取失败：${adjusted_image}${NC}"
        return 1
    fi

    # 保存镜像
    if docker save -o "$output_path" "$adjusted_image"; then
        echo -e "${GREEN}镜像已保存到：${output_path}${NC}"
        return 0
    else
        echo -e "${RED}保存失败：${output_path}${NC}"
        return 1
    fi
}

# 打印执行信息
echo -e "${BLUE}==============================${NC}"
echo -e "${YELLOW}架构\t: ${ARCH_SUFFIX}${NC}"
echo -e "${YELLOW}版本\t: ${eulercopilot_version}${NC}"
echo -e "${YELLOW}存储目录\t: ${OUTPUT_DIR}${NC}"
echo -e "${YELLOW}镜像数量\t: ${total}${NC}"
echo -e "${BLUE}==============================${NC}"

# 遍历处理所有镜像
for index in "${!BASE_IMAGES[@]}"; do
    if process_image "${BASE_IMAGES[$index]}" "${FILE_NAMES[$index]}"; then
        ((success++))
    else
        ((fail++))
    fi
done

# 输出最终结果
echo -e "\n${BLUE}==============================${NC}"
echo -e "${GREEN}操作完成！${NC}"
echo -e "${BLUE}==============================${NC}"
echo -e "${GREEN}成功\t: ${success} 个${NC}"
echo -e "${RED}失败\t: ${fail} 个${NC}"
echo -e "${BLUE}==============================${NC}"

# 返回状态码
exit $((fail > 0 ? 1 : 0))
