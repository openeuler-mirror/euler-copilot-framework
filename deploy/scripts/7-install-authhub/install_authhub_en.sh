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

# Print help information
print_help() {
    echo -e "${GREEN}Usage: $0 [options]"
    echo -e "Options:"
    echo -e "  --help                      Show help information"
    echo -e "  --authhub_address <address> Specify Authhub access address (e.g.: http://myhost:30081)"
    echo -e ""
    echo -e "Example:"
    echo -e "  $0 --authhub_address http://myhost:30081${NC}"
    exit 0
}

# Get system architecture
get_architecture() {
    local arch=$(uname -m)
    case "$arch" in
        x86_64)
            arch="x86"
            ;;
        aarch64)
            arch="arm"
            ;;
        *)
            echo -e "${RED}Error: Unsupported architecture $arch${NC}" >&2
            return 1
            ;;
    esac
    echo -e "${GREEN}Detected system architecture: $(uname -m)${NC}" >&2
    echo "$arch"
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

uninstall_authhub() {
    echo -e "${BLUE}==> Cleaning up existing resources...${NC}"

    local RELEASES
    RELEASES=$(helm list -n euler-copilot --short | grep authhub || true)

    if [ -n "$RELEASES" ]; then
        echo -e "${YELLOW}Found Helm Releases, starting cleanup...${NC}"
        for release in $RELEASES; do
            echo -e "${BLUE}Deleting Helm Release: ${release}${NC}"
            helm uninstall "$release" -n euler-copilot || echo -e "${RED}Failed to delete Helm Release, continuing...${NC}"
        done
    else
        echo -e "${YELLOW}No Helm Releases found to clean${NC}"
    fi

    local pvc_name
    pvc_name=$(kubectl get pvc -n euler-copilot | grep 'mysql-pvc' 2>/dev/null || true)

    if [ -n "$pvc_name" ]; then
        echo -e "${YELLOW}Found PVCs, starting cleanup...${NC}"
        kubectl delete pvc mysql-pvc -n euler-copilot --force --grace-period=0 || echo -e "${RED}PVC deletion failed, continuing...${NC}"
    else
        echo -e "${YELLOW}No PVCs found to clean${NC}"
    fi

    # New: Delete authhub-secret
    local authhub_secret="authhub-secret"
    if kubectl get secret "$authhub_secret" -n euler-copilot &>/dev/null; then
        echo -e "${YELLOW}Found Secret: ${authhub_secret}, starting cleanup...${NC}"
        if ! kubectl delete secret "$authhub_secret" -n euler-copilot; then
            echo -e "${RED}Error: Failed to delete Secret ${authhub_secret}!${NC}" >&2
            return 1
        fi
    else
        echo -e "${YELLOW}No Secret found to clean: ${authhub_secret}${NC}"
    fi

    echo -e "${GREEN}Resource cleanup completed${NC}"
}

get_authhub_address() {
    local default_address="http://127.0.0.1:30081"

    echo -e "${BLUE}Enter Authhub access address (IP or domain)${NC}"
    read -p "Authhub address: " authhub_address

    # Handle empty input
    if [[ -z "$authhub_address" ]]; then
        authhub_address="$default_address"
        echo -e "${GREEN}Using default address: ${authhub_address}${NC}"
    else
        echo -e "${GREEN}Input address: ${authhub_address}${NC}"
    fi

    return 0
}

helm_install() {
    local arch="$1"
    echo -e "${BLUE}==> Entering deployment directory...${NC}"
    [ ! -d "${CHART_DIR}" ] && {
        echo -e "${RED}Error: Deployment directory does not exist ${CHART_DIR} ${NC}"
        return 1
    }
    cd "${CHART_DIR}"

    echo -e "${BLUE}Installing authhub...${NC}"
    helm upgrade --install authhub -n euler-copilot ./authhub \
        --set globals.arch="$arch" \
        --set domain.authhub="${authhub_address}" || {
        echo -e "${RED}Helm installation of authhub failed!${NC}"
        return 1
    }
}

check_pods_status() {
    echo -e "${BLUE}==> Waiting for initialization (30 seconds)...${NC}" >&2
    sleep 30

    local timeout=300
    local start_time=$(date +%s)

    echo -e "${BLUE}Monitoring pod status (total timeout 300 seconds)...${NC}" >&2

    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [ $elapsed -gt $timeout ]; then
            echo -e "${YELLOW}Warning: Deployment timeout! Please check the following resources:${NC}" >&2
            kubectl get pods -n euler-copilot -o wide
            echo -e "\n${YELLOW}Suggestions:${NC}"
            echo "1. Check logs of unready pods: kubectl logs -n euler-copilot <pod-name>"
            echo "2. Check PVC status: kubectl get pvc -n euler-copilot"
            echo "3. Check Service status: kubectl get svc -n euler-copilot"
            return 1
        fi

        local not_running=$(kubectl get pods -n euler-copilot -o jsonpath='{range .items[*]}{.metadata.name} {.status.phase} {.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' \
            | awk '$2 != "Running" || $3 != "True" {print $1 " " $2}')

        if [ -z "$not_running" ]; then
            echo -e "${GREEN}All pods are running normally!${NC}" >&2
            kubectl get pods -n euler-copilot -o wide
            return 0
        else
            echo "Waiting for pods to be ready (waited ${elapsed} seconds)..."
            echo "Current unready pods:"
            echo "$not_running" | awk '{print "  - " $1 " (" $2 ")"}'
            sleep 10
        fi
    done
}

deploy() {
    local arch
    arch=$(get_architecture) || exit 1
    create_namespace || exit 1
    uninstall_authhub || exit 1

    # If address not provided via parameter, prompt user
    if [ -z "$authhub_address" ]; then
        echo -e "${YELLOW}--authhub_address parameter not provided, need manual input${NC}"
        get_authhub_address || exit 1
    else
        echo -e "${GREEN}Using parameter-specified Authhub address: $authhub_address${NC}"
    fi

    helm_install "$arch" || exit 1
    check_pods_status || {
        echo -e "${RED}Deployment failed: Pod status check not passed!${NC}"
        exit 1
    }

    echo -e "\n${GREEN}========================="
    echo -e "Authhub deployment completed!"
    echo -e "Check pod status: kubectl get pod -n euler-copilot"
    echo -e "Authhub login address: $authhub_address"
    echo -e "Default credentials: administrator/changeme"
    echo -e "=========================${NC}"
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help)
                print_help
                exit 0
                ;;
            --authhub_address)
                if [ -n "$2" ]; then
                    authhub_address="$2"
                    shift 2
                else
                    echo -e "${RED}Error: --authhub_address requires a parameter${NC}" >&2
                    exit 1
                fi
                ;;
            *)
                echo -e "${RED}Unknown parameter: $1${NC}" >&2
                print_help
                exit 1
                ;;
        esac
    done
}

main() {
    parse_args "$@"
    deploy
}

trap 'echo -e "${RED}Operation interrupted!${NC}"; exit 1' INT
main "$@"
