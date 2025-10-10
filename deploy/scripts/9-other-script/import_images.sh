#!/bin/bash

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # Reset color

# Default configuration
DEFAULT_VERSION="0.9.5"
IMAGE_BASE_DIR="/home/eulercopilot/images"

# Show help information
show_help() {
    echo -e "${YELLOW}Usage:${NC}"
    echo -e "  $0 [options] [parameters]"
    echo -e "${YELLOW}Options:${NC}"
    echo -e "  -v, --version <version>\tSpecify image version (default: ${DEFAULT_VERSION})"
    echo -e "  -i, --import <file>\t\tImport single image file"
    echo -e "  -d, --delete <image>\t\tDelete specified image (format: repo/image:tag)"
    echo -e "  --delete-all\t\t\tDelete all neocopilot images"
    echo -e "  -h, --help\t\t\tShow help information"
    echo -e "${YELLOW}Examples:${NC}"
    echo -e "  $0 -v 0.9.4\t\t\tImport version 0.9.4 images"
    echo -e "  $0 -i $IMAGE_BASE_DIR/$DEFAULT_VERSION/myimage.tar\tImport single image file"
    echo -e "  $0 -d hub.oepkgs.net/neocopilot/authhub:0.9.3-arm\tDelete specified image"
    echo -e "  $0 --delete-all\t\tDelete all neocopilot images"
    exit 0
}

# Parameter parsing
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
                echo -e "${RED}Unknown parameter: $1${NC}"
                show_help
                exit 1
                ;;
        esac
    done
}

# System architecture detection
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
            echo -e "${RED}Unsupported architecture: $ARCH${NC}"
            exit 1
            ;;
    esac
}

# Delete specified image
delete_image() {
    local image=$1
    echo -e "${YELLOW}Deleting image: $image${NC}"
    if sudo k3s ctr -n=k8s.io images rm "$image"; then
        echo -e "${GREEN} Deletion successful${NC}"
    else
        echo -e "${RED} Deletion failed${NC}"
    fi
}

# Delete all neocopilot images
delete_all_neocopilot_images() {
    echo -e "${YELLOW}Deleting all neocopilot images...${NC}"
    sudo k3s crictl images | grep neocopilot | awk '{print $1":"$2}' | while read -r image; do
        delete_image "$image"
    done
}

# Import single image file
import_single_image() {
    local file=$1
    echo -e "${CYAN}Importing single image: $file${NC}"

    if [[ ! -f "$file" ]]; then
        echo -e "${RED}Error: File does not exist $file${NC}"
        exit 1
    fi

    if sudo k3s ctr -n=k8s.io images import "$file"; then
        echo -e "${GREEN} Import successful${NC}"
    else
        echo -e "${RED} Import failed${NC}"
        exit 1
    fi
}

# Batch import images
batch_import_images() {
    local version=$1
    local image_dir="$IMAGE_BASE_DIR/$version"

    if [[ ! -d "$image_dir" ]]; then
        echo -e "${RED}Error: Image directory does not exist $image_dir${NC}"
        exit 1
    fi

    echo -e "${CYAN}Scanning directory: $image_dir${NC}"
    echo -e "${CYAN}Found the following TAR files:${NC}"
    ls -1 "$image_dir"/*.tar

    local success_count=0
    local fail_count=0

    for tar_file in "$image_dir"/*.tar; do
        [[ -f "$tar_file" ]] || continue

        echo -e "\n${BLUE}Importing $tar_file...${NC}"

        if sudo k3s ctr -n=k8s.io images import "$tar_file"; then
            ((success_count++))
            echo -e "${GREEN} Import successful${NC}"
        else
            ((fail_count++))
            echo -e "${RED} Import failed${NC}"
        fi
    done

    echo -e "\n${CYAN}Import results:${NC}"
    echo -e "${GREEN}Successful: $success_count${NC}"
    echo -e "${RED}Failed: $fail_count${NC}"

    return $fail_count
}

# Image integrity check
check_images() {
    local version=$1
    local missing_count=0

    # Base image list (using version variable)
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

    # Adjust expected image tags based on architecture
    local expected_images=()
    for image in "${base_images[@]}"; do
        if [[ "$ARCH_SUFFIX" == "x86" ]]; then
            expected_image="${image/-arm/-x86}"
        else
            expected_image="$image"
        fi
        expected_images+=("$expected_image")
    done

    echo -e "\n${MAGENTA}Starting image integrity check:${NC}"
    for image in "${expected_images[@]}"; do
        if sudo k3s ctr -n=k8s.io images ls | grep -q "$image"; then
            echo -e "${GREEN}[Exists] $image${NC}"
        else
            echo -e "${RED}[Missing] $image${NC}"
            ((missing_count++))
        fi
    done

    echo -e "\n${MAGENTA}Checking images with crictl:${NC}"
    sudo k3s crictl images | grep neocopilot

    if [[ $missing_count -gt 0 ]]; then
        echo -e "\n${RED}Warning: Missing $missing_count required images${NC}"
        return 1
    else
        echo -e "\n${GREEN}All required images are ready${NC}"
        return 0
    fi
}

# Main function
main() {
    parse_args "$@"
    detect_architecture

    # Handle delete operations
    if [[ -n "$image_to_delete" ]]; then
        delete_image "$image_to_delete"
        exit 0
    fi

    if [[ "$delete_all_images" == true ]]; then
        delete_all_neocopilot_images
        exit 0
    fi

    # Handle single image import
    if [[ -n "$single_image_file" ]]; then
        import_single_image "$single_image_file"
        exit 0
    fi

    # Default batch import mode
    local version=${eulercopilot_version:-$DEFAULT_VERSION}

    echo -e "${YELLOW}==============================${NC}"
    echo -e "${CYAN}Architecture\t: ${ARCH_SUFFIX}${NC}"
    echo -e "${CYAN}Target version\t: ${version}${NC}"
    echo -e "${CYAN}Image directory\t: ${IMAGE_BASE_DIR}/${version}${NC}"
    echo -e "${YELLOW}==============================${NC}"

    batch_import_images "$version"
    import_result=$?

    if [[ $import_result -eq 0 ]]; then
        check_images "$version" || exit 1
    else
        echo -e "${RED}Some images failed to import, skipping integrity check${NC}"
        exit 1
    fi

    echo -e "${GREEN}System ready, all images available${NC}"
}

# Execute main function
main "$@"
exit 0
