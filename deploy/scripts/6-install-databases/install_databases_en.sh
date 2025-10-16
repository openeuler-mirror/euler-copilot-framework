#!/bin/bash
set -eo pipefail

RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
NC='\033[0m'

SCRIPT_PATH="$(
  cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1
  pwd
)/$(basename "${BASH_SOURCE[0]}")"

CHART_DIR="$(
  canonical_path=$(readlink -f "$SCRIPT_PATH" 2>/dev/null || echo "$SCRIPT_PATH")
  dirname "$(dirname "$(dirname "$canonical_path")")"
)/chart"

# Get system architecture
get_architecture() {
    arch=$(uname -m)
    case "$arch" in
        x86_64)
            arch="x86"
            ;;
        aarch64)
            arch="arm"
            ;;
        *)
            echo -e "${RED}Error: Unsupported architecture $arch${NC}"
            exit 1
            ;;
    esac
    echo -e "${GREEN}Detected system architecture: $(uname -m)${NC}"
}

create_namespace() {
    echo -e "${BLUE}==> Checking namespace euler-copilot...${NC}"
    if ! kubectl get namespace euler-copilot &> /dev/null; then
        kubectl create namespace euler-copilot || {
            echo -e "${RED}Namespace creation failed!${NC}"
            return 1
        }
        echo -e "${GREEN}Namespace created successfully${NC}"
    else
        echo -e "${YELLOW}Namespace already exists, skipping creation${NC}"
    fi
}

uninstall_databases() {
    echo -e "${BLUE}==> Cleaning up existing resources...${NC}"

    local helm_releases
    helm_releases=$(helm list -n euler-copilot -q --filter '^databases' 2>/dev/null || true)

    if [ -n "$helm_releases" ]; then
        echo -e "${YELLOW}Found the following Helm Releases, starting cleanup...${NC}"
        while IFS= read -r release; do
            echo -e "${BLUE}Deleting Helm Release: ${release}${NC}"
            if ! helm uninstall "$release" -n euler-copilot --wait --timeout 2m; then
                echo -e "${RED}Error: Failed to delete Helm Release ${release}!${NC}" >&2
                return 1
            fi
        done <<< "$helm_releases"
    else
        echo -e "${YELLOW}No Helm Releases found to clean${NC}"
    fi

    # Modified: Only filter specific PVC names
    local pvc_list
    pvc_list=$(kubectl get pvc -n euler-copilot -o jsonpath='{.items[*].metadata.name}' 2>/dev/null \
        | tr ' ' '\n' \
        | grep -E '^(opengauss-storage|mongo-storage|minio-storage)$' || true)  # Exact match for three specified names

    if [ -n "$pvc_list" ]; then
        echo -e "${YELLOW}Found the following PVCs, starting cleanup...${NC}"
        while IFS= read -r pvc; do
            echo -e "${BLUE}Deleting PVC: $pvc${NC}"
            if ! kubectl delete pvc "$pvc" -n euler-copilot --force --grace-period=0; then
                echo -e "${RED}Error: Failed to delete PVC $pvc!${NC}" >&2
                return 1
            fi
        done <<< "$pvc_list"
    else
        echo -e "${YELLOW}No PVCs found to clean${NC}"
    fi

    # New: Delete euler-copilot-database Secret
    local secret_name="euler-copilot-database"
    if kubectl get secret "$secret_name" -n euler-copilot &>/dev/null; then
        echo -e "${YELLOW}Found Secret: ${secret_name}, starting cleanup...${NC}"
        if ! kubectl delete secret "$secret_name" -n euler-copilot; then
            echo -e "${RED}Error: Failed to delete Secret ${secret_name}!${NC}" >&2
            return 1
        fi
    else
        echo -e "${YELLOW}No Secret found to clean: ${secret_name}${NC}"
    fi

    echo -e "${BLUE}Waiting for resource cleanup to complete (10 seconds)...${NC}"
    sleep 10

    echo -e "${GREEN}Resource cleanup completed${NC}"
}

helm_install() {
    echo -e "${BLUE}==> Entering deployment directory...${NC}"
    [ ! -d "$CHART_DIR" ] && {
        echo -e "${RED}Error: Deployment directory does not exist $CHART_DIR${NC}"
        return 1
    }
    cd "$CHART_DIR"

    echo -e "${BLUE}Installing databases...${NC}"
    helm upgrade --install databases --set globals.arch=$arch -n euler-copilot ./databases || {
        echo -e "${RED}Helm installation of databases failed!${NC}"
        return 1
    }
}

check_pods_status() {
    echo -e "${BLUE}==> Waiting for initialization to complete (30 seconds)...${NC}"
    sleep 30

    local timeout=300
    local start_time=$(date +%s)

    echo -e "${BLUE}Starting pod status monitoring (total timeout 300 seconds)...${NC}"

    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [ $elapsed -gt $timeout ]; then
            echo -e "${RED}Error: Deployment timeout!${NC}"
            kubectl get pods -n euler-copilot
            return 1
        fi

        local not_running=$(kubectl get pods -n euler-copilot -o jsonpath='{range .items[*]}{.metadata.name} {.status.phase}{"\n"}{end}' | grep -v "Running")

        if [ -z "$not_running" ]; then
            echo -e "${GREEN}All pods are running normally!${NC}"
            kubectl get pods -n euler-copilot
            return 0
        else
            echo "Waiting for pods to be ready (waited ${elapsed} seconds)..."
            echo "Current abnormal pods:"
            echo "$not_running" | awk '{print "  - " $1 " (" $2 ")"}'
            sleep 10
        fi
    done
}

main() {
    get_architecture
    create_namespace
    uninstall_databases
    helm_install
    check_pods_status

    echo -e "\n${GREEN}========================="
    echo "Database deployment completed!"
    echo -e "=========================${NC}"
}

trap 'echo -e "${RED}Operation interrupted!${NC}"; exit 1' INT
main "$@"
