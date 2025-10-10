#!/bin/bash

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # Reset color

# Default configuration
eulercopilot_version="0.10.0"
ARCH_SUFFIX=""
OUTPUT_DIR="/home/eulercopilot/images/${eulercopilot_version}"

# Show help information
show_help() {
    echo -e "${YELLOW}Usage:${NC}"
    echo -e "  $0 [options]"
    echo -e ""
    echo -e "${YELLOW}Options:${NC}"
    echo -e "  --help            Show this help message"
    echo -e "  --version <version> Specify EulerCopilot version (default: ${eulercopilot_version})"
    echo -e "  --arch <arch>     Specify system architecture (arm/x86, default: auto-detect)"
    echo -e ""
    echo -e "${YELLOW}Examples:${NC}"
    echo -e "  $0 --version ${eulercopilot_version} --arch arm"
    echo -e "  $0 --help"
    exit 0
}

# Parse command line arguments
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
                echo -e "${RED}Error: --version requires a version number${NC}"
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
                        echo -e "${RED}Error: Unsupported architecture '$2', must be arm or x86${NC}"
                        exit 1
                        ;;
                esac
                shift
            else
                echo -e "${RED}Error: --arch requires an architecture (arm/x86)${NC}"
                exit 1
            fi
            ;;
        *)
            echo -e "${RED}Unknown parameter: $1${NC}"
            show_help
            ;;
    esac
    shift
done

# Auto-detect architecture (if not specified via parameter)
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
            echo -e "${RED}Unsupported architecture: $ARCH${NC}"
            exit 1
            ;;
    esac
fi

mkdir -p "$OUTPUT_DIR"

# Image list (using version variable)
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

# Predefined filename list (strictly corresponding to BASE_IMAGES order)
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

# Validate list consistency
if [ ${#BASE_IMAGES[@]} -ne ${#FILE_NAMES[@]} ]; then
    echo -e "${RED}Error: Image list and filename list count mismatch${NC}"
    exit 1
fi

# Initialize counters
total=${#BASE_IMAGES[@]}
success=0
fail=0

# Image processing function
process_image() {
    local raw_image=$1
    local filename=$2

    # Adjust architecture tag
    local adjusted_image="${raw_image/-arm/-${ARCH_SUFFIX}}"
    local output_path="${OUTPUT_DIR}/${filename}"

    echo -e "\n${BLUE}Processing: ${adjusted_image}${NC}"

    # Pull image
    if ! docker pull "$adjusted_image"; then
        echo -e "${RED}Pull failed: ${adjusted_image}${NC}"
        return 1
    fi

    # Save image
    if docker save -o "$output_path" "$adjusted_image"; then
        echo -e "${GREEN}Image saved to: ${output_path}${NC}"
        return 0
    else
        echo -e "${RED}Save failed: ${output_path}${NC}"
        return 1
    fi
}

# Print execution information
echo -e "${BLUE}==============================${NC}"
echo -e "${YELLOW}Architecture\t: ${ARCH_SUFFIX}${NC}"
echo -e "${YELLOW}Version\t\t: ${eulercopilot_version}${NC}"
echo -e "${YELLOW}Storage directory\t: ${OUTPUT_DIR}${NC}"
echo -e "${YELLOW}Image count\t: ${total}${NC}"
echo -e "${BLUE}==============================${NC}"

# Process all images
for index in "${!BASE_IMAGES[@]}"; do
    if process_image "${BASE_IMAGES[$index]}" "${FILE_NAMES[$index]}"; then
        ((success++))
    else
        ((fail++))
    fi
done

# Output final result
echo -e "\n${BLUE}==============================${NC}"
echo -e "${GREEN}Operation completed!${NC}"
echo -e "${BLUE}==============================${NC}"
echo -e "${GREEN}Success\t: ${success}${NC}"
echo -e "${RED}Failed\t: ${fail}${NC}"
echo -e "${BLUE}==============================${NC}"

# Return status code
exit $((fail > 0 ? 1 : 0))
