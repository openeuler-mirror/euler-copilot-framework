#!/bin/bash

set -eo pipefail

# Color definitions
RED='\e[31m'
GREEN='\e[32m'
YELLOW='\e[33m'
BLUE='\e[34m'
NC='\e[0m' # Reset color

NAMESPACE="euler-copilot"
PLUGINS_DIR="/var/lib/eulercopilot"

# Global variables
client_id=""
client_secret=""
eulercopilot_address=""
authhub_address=""

SCRIPT_PATH="$(
  cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1
  pwd
)/$(basename "${BASH_SOURCE[0]}")"

DEPLOY_DIR="$(
  canonical_path=$(readlink -f "$SCRIPT_PATH" 2>/dev/null || echo "$SCRIPT_PATH")
  dirname "$(dirname "$(dirname "$canonical_path")")"
)"

# Show help information
show_help() {
    echo -e "${GREEN}Usage: $0 [options]"
    echo -e "Options:"
    echo -e "  --help                   Show this help message"
    echo -e "  --eulercopilot_address   Specify EulerCopilot frontend access URL"
    echo -e "  --authhub_address        Specify Authhub frontend access URL"
    echo -e ""
    echo -e "Example:"
    echo -e "  $0 --eulercopilot_address http://myhost:30080 --authhub_address http://myhost:30081${NC}"
    exit 0
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help)
                show_help
                ;;
            --eulercopilot_address)
                if [ -n "$2" ]; then
                    eulercopilot_address="$2"
                    shift
                else
                    echo -e "${RED}Error: --eulercopilot_address requires a value${NC}" >&2
                    exit 1
                fi
                ;;
            --authhub_address)
                if [ -n "$2" ]; then
                    authhub_address="$2"
                    shift
                else
                    echo -e "${RED}Error: --authhub_address requires a value${NC}" >&2
                    exit 1
                fi
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}" >&2
                show_help
                exit 1
                ;;
        esac
        shift
    done
}

# Get system architecture
get_architecture() {
    local arch=$(uname -m)
    case "$arch" in
        x86_64)  arch="x86" ;;
        aarch64) arch="arm" ;;
        *)
            echo -e "${RED}Error: Unsupported architecture $arch${NC}" >&2
            return 1
            ;;
    esac
    echo -e "${GREEN}Detected system architecture: ${arch} (original: $(uname -m))${NC}" >&2
    echo "$arch"
}

# Auto-detect business network interface
get_network_ip() {
    echo -e "${BLUE}Auto-detecting business network interface IP address...${NC}" >&2
    local timeout=20
    local start_time=$(date +%s)
    local interface=""
    local host=""

    # Find available network interfaces
    while [ $(( $(date +%s) - start_time )) -lt $timeout ]; do
        # Get all non-virtual interfaces (exclude lo, docker, veth, etc.)
        interfaces=$(ip -o link show | awk -F': ' '{print $2}' | grep -vE '^lo$|docker|veth|br-|virbr|tun')

        for intf in $interfaces; do
            # Check if interface status is UP
            if ip link show "$intf" | grep -q 'state UP'; then
                # Get IPv4 address
                ip_addr=$(ip addr show "$intf" | grep -w inet | awk '{print $2}' | cut -d'/' -f1)
                if [ -n "$ip_addr" ]; then
                    interface=$intf
                    host=$ip_addr
                    break 2 # Break two levels
                fi
            fi
        done
        sleep 1
    done

    if [ -z "$interface" ]; then
        echo -e "${RED}Error: No available business network interface found${NC}" >&2
        exit 1
    fi

    echo -e "${GREEN}Using network interface: ${interface}, IP address: ${host}${NC}" >&2
    echo "$host"
}

get_address_input() {
    # If addresses already provided via command line, use them directly
    if [ -n "$eulercopilot_address" ] && [ -n "$authhub_address" ]; then
        echo -e "${GREEN}Using command line parameters:"
        echo "EulerCopilot address: $eulercopilot_address"
        echo "Authhub address:     $authhub_address"
        return
    fi

    # Read from environment variables or use defaults
    eulercopilot_address=${EULERCOPILOT_ADDRESS:-"http://127.0.0.1:30080"}
    authhub_address=${AUTHHUB_ADDRESS:-"http://127.0.0.1:30081"}

    # Non-interactive mode uses defaults directly
    if [ -t 0 ]; then  # Only show prompts in interactive terminal
        echo -e "${BLUE}Enter EulerCopilot frontend access URL (default: $eulercopilot_address):${NC}"
        read -p "> " input_euler
        [ -n "$input_euler" ] && eulercopilot_address=$input_euler

        echo -e "${BLUE}Enter Authhub frontend access URL (default: $authhub_address):${NC}"
        read -p "> " input_auth
        [ -n "$input_auth" ] && authhub_address=$input_auth
    fi

    echo -e "${GREEN}Using configuration:"
    echo "EulerCopilot address: $eulercopilot_address"
    echo "Authhub address:     $authhub_address"
}

get_client_info_auto() {
    # Get user input addresses
    get_address_input
    # Create temporary file
    local temp_file
    temp_file=$(mktemp)

    # Directly call Python script and pass domain parameters
    python3 "${DEPLOY_DIR}/scripts/9-other-script/get_client_id_and_secret.py" "${eulercopilot_address}" > "$temp_file" 2>&1

    # Check Python script execution result
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Python script execution failed${NC}"
        cat "$temp_file"
        rm -f "$temp_file"
        return 1
    fi

    # Extract credential information
    client_id=$(grep "client_id: " "$temp_file" | awk '{print $2}')
    client_secret=$(grep "client_secret: " "$temp_file" | awk '{print $2}')
    rm -f "$temp_file"

    # Verify results
    if [ -z "$client_id" ] || [ -z "$client_secret" ]; then
        echo -e "${RED}Error: Unable to get valid client credentials${NC}" >&2
        return 1
    fi

    # Output results
    echo -e "${GREEN}==============================${NC}"
    echo -e "${GREEN}Client ID:     ${client_id}${NC}"
    echo -e "${GREEN}Client Secret: ${client_secret}${NC}"
    echo -e "${GREEN}==============================${NC}"
}

get_client_info_manual() {
    # Non-interactive mode uses defaults directly
    if [ -t 0 ]; then  # Only show prompts in interactive terminal
        echo -e "${BLUE}Enter Client ID: domain (endpoint info: Client ID): ${NC}"
        read -p "> " input_id
        [ -n "$input_id" ] && client_id=$input_id

        echo -e "${BLUE}Enter Client Secret: domain (endpoint info: Client Secret):${NC}"
        read -p "> " input_secret
        [ -n "$input_secret" ] && client_secret=$input_secret
    fi

    # Unified domain format verification
    echo -e "${GREEN}Using configuration:"
    echo "Client ID: $client_id"
    echo "Client Secret: $client_secret"
}

check_directories() {
    echo -e "${BLUE}Checking if semantic interface directory exists...${NC}" >&2

    # Define parent directory and subdirectory list
    local REQUIRED_OWNER="root:root"

    # Check and create parent directory
    if [ -d "${PLUGINS_DIR}" ]; then
        echo -e "${GREEN}Directory exists: ${PLUGINS_DIR}${NC}" >&2
        # Check current permissions
        local current_owner=$(stat -c "%u:%g" "${PLUGINS_DIR}" 2>/dev/null)
        if [ "$current_owner" != "$REQUIRED_OWNER" ]; then
            echo -e "${YELLOW}Current directory permissions: ${current_owner}, modifying to ${REQUIRED_OWNER}...${NC}" >&2
            if chown root:root "${PLUGINS_DIR}"; then
                echo -e "${GREEN}Directory permissions successfully modified to ${REQUIRED_OWNER}${NC}" >&2
            else
                echo -e "${RED}Error: Unable to modify directory permissions to ${REQUIRED_OWNER}${NC}" >&2
                exit 1
            fi
        else
            echo -e "${GREEN}Directory permissions correct (${REQUIRED_OWNER})${NC}" >&2
        fi
    else
        if mkdir -p "${PLUGINS_DIR}"; then
            echo -e "${GREEN}Directory created: ${PLUGINS_DIR}${NC}" >&2
            chown root:root "${PLUGINS_DIR}"  # Set parent directory owner
        else
            echo -e "${RED}Error: Unable to create directory ${PLUGINS_DIR}${NC}" >&2
            exit 1
        fi
    fi
}

uninstall_eulercopilot() {
    echo -e "${YELLOW}Checking if EulerCopilot is already deployed...${NC}" >&2

    # Delete Helm Release: euler-copilot
    if helm list -n euler-copilot --short | grep -q '^euler-copilot$'; then
        echo -e "${GREEN}Found Helm Release: euler-copilot, starting cleanup...${NC}"
        if ! helm uninstall euler-copilot -n euler-copilot; then
            echo -e "${RED}Error: Failed to delete Helm Release euler-copilot!${NC}" >&2
            return 1
        fi
    else
        echo -e "${YELLOW}No Helm Release found to clean: euler-copilot${NC}"
    fi

    # Delete PVC: framework-semantics-claim
    local pvc_name="framework-semantics-claim"
    if kubectl get pvc "$pvc_name" -n euler-copilot &>/dev/null; then
        echo -e "${GREEN}Found PVC: ${pvc_name}, starting cleanup...${NC}"
        if ! kubectl delete pvc "$pvc_name" -n euler-copilot --force --grace-period=0; then
            echo -e "${RED}Error: Failed to delete PVC ${pvc_name}!${NC}" >&2
            return 1
        fi
    else
        echo -e "${YELLOW}No PVC found to clean: ${pvc_name}${NC}"
    fi

    # Delete Secret: euler-copilot-system
    local secret_name="euler-copilot-system"
    if kubectl get secret "$secret_name" -n euler-copilot &>/dev/null; then
        echo -e "${GREEN}Found Secret: ${secret_name}, starting cleanup...${NC}"
        if ! kubectl delete secret "$secret_name" -n euler-copilot; then
            echo -e "${RED}Error: Failed to delete Secret ${secret_name}!${NC}" >&2
            return 1
        fi
    else
        echo -e "${YELLOW}No Secret found to clean: ${secret_name}${NC}"
    fi

    echo -e "${GREEN}Resource cleanup completed${NC}"
}

modify_yaml() {
    local host=$1
    local preserve_models=$2  # New parameter, indicates whether to preserve model configuration
    echo -e "${BLUE}Starting YAML configuration file modification...${NC}" >&2

    # Build parameter array
    local set_args=()

    # Add other required parameters
    set_args+=(
        "--set" "login.client.id=${client_id}"
        "--set" "login.client.secret=${client_secret}"
        "--set" "domain.euler_copilot=${eulercopilot_address}"
        "--set" "domain.authhub=${authhub_address}"
    )

    # If model configuration doesn't need to be preserved, add model-related parameters
    if [[ "$preserve_models" != [Yy]* ]]; then
        set_args+=(
            "--set" "models.answer.endpoint=http://$host:11434/v1"
            "--set" "models.answer.key=sk-123456"
            "--set" "models.answer.name=deepseek-llm-7b-chat:latest"
            "--set" "models.functionCall.backend=ollama"
            "--set" "models.functionCall.endpoint=http://$host:11434"
            "--set" "models.embedding.type=openai"
            "--set" "models.embedding.endpoint=http://$host:11434/v1"
            "--set" "models.embedding.key=sk-123456"
            "--set" "models.embedding.name=bge-m3:latest"
        )
    fi

    # Call Python script, pass all parameters
    python3 "${DEPLOY_DIR}/scripts/9-other-script/modify_eulercopilot_yaml.py" \
      "${DEPLOY_DIR}/chart/euler_copilot/values.yaml" \
      "${DEPLOY_DIR}/chart/euler_copilot/values.yaml" \
      "${set_args[@]}" || {
        echo -e "${RED}Error: YAML file modification failed${NC}" >&2
        exit 1
    }
    echo -e "${GREEN}YAML file modified successfully!${NC}" >&2
}

# Check directory
enter_chart_directory() {
    echo -e "${BLUE}Entering Chart directory...${NC}" >&2
    cd "${DEPLOY_DIR}/chart/" || {
        echo -e "${RED}Error: Unable to enter Chart directory ${DEPLOY_DIR}/chart/${NC}" >&2
        exit 1
    }
}

pre_install_checks() {
    # Check if kubectl and helm are available
    command -v kubectl >/dev/null 2>&1 || error_exit "kubectl not installed"
    command -v helm >/dev/null 2>&1 || error_exit "helm not installed"

    # Check Kubernetes cluster connection
    kubectl cluster-info >/dev/null 2>&1 || error_exit "Unable to connect to Kubernetes cluster"

    # Check necessary storage classes
    kubectl get storageclasses >/dev/null 2>&1 || error_exit "Unable to get storage class information"
}

# Execute installation
execute_helm_install() {
    local arch=$1
    echo -e "${BLUE}Starting EulerCopilot deployment (architecture: $arch)...${NC}" >&2

    enter_chart_directory
    helm upgrade --install $NAMESPACE -n $NAMESPACE ./euler_copilot --set globals.arch=$arch --create-namespace || {
        echo -e "${RED}Helm installation of EulerCopilot failed!${NC}" >&2
        exit 1
    }
    echo -e "${GREEN}Helm installation of EulerCopilot successful!${NC}" >&2
}

# Check pod status
check_pods_status() {
    echo -e "${BLUE}==> Waiting for initialization (30 seconds)...${NC}" >&2
    sleep 30

    local timeout=300
    local start_time=$(date +%s)

    echo -e "${BLUE}Starting pod status monitoring (total timeout 300 seconds)...${NC}" >&2

    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [ $elapsed -gt $timeout ]; then
            echo -e "${YELLOW}Warning: Deployment timeout! Please check the following resources:${NC}" >&2
            kubectl get pods -n $NAMESPACE -o wide
            echo -e "\n${YELLOW}Suggested checks:${NC}"
            echo "1. Check logs of unready pods: kubectl logs -n $NAMESPACE <pod-name>"
            echo "2. Check PVC status: kubectl get pvc -n $NAMESPACE"
            echo "3. Check Service status: kubectl get svc -n $NAMESPACE"
            return 1
        fi

        local not_running=$(kubectl get pods -n $NAMESPACE -o jsonpath='{range .items[*]}{.metadata.name} {.status.phase} {.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' \
            | awk '$2 != "Running" || $3 != "True" {print $1 " " $2}')

        if [ -z "$not_running" ]; then
            echo -e "${GREEN}All pods are running normally!${NC}" >&2
            kubectl get pods -n $NAMESPACE -o wide
            return 0
        else
            echo "Waiting for pods to be ready (waited ${elapsed} seconds)..."
            echo "Current unready pods:"
            echo "$not_running" | awk '{print "  - " $1 " (" $2 ")"}'
            sleep 10
        fi
    done
}

# Modify main function
main() {
    parse_arguments "$@"

    pre_install_checks

    local arch host
    arch=$(get_architecture) || exit 1
    host=$(get_network_ip) || exit 1

    uninstall_eulercopilot

    if ! get_client_info_auto; then
        get_client_info_manual
    fi

    check_directories

    # Interactive prompt optimization
    if [ -t 0 ]; then
        echo -e "${YELLOW}Keep existing model configuration?${NC}"
        echo -e "  ${BLUE}Y) Keep existing configuration${NC}"
        echo -e "  ${BLUE}n) Use default configuration${NC}"
        while true; do
            read -p "Please choose (Y/N): " input_preserve
            case "${input_preserve:-Y}" in
                [YyNn]) preserve_models=${input_preserve:-Y}; break ;;
                *) echo -e "${RED}Invalid input, please choose Y or n${NC}" ;;
            esac
        done
    else
        preserve_models="N"
    fi

    echo -e "${BLUE}Starting YAML configuration modification...${NC}"
    modify_yaml "$host" "$preserve_models"

    echo -e "${BLUE}Starting Helm installation...${NC}"
    execute_helm_install "$arch"

    if check_pods_status; then
        echo -e "${GREEN}All components are ready!${NC}"
        show_success_message "$host" "$arch"
    else
        echo -e "${YELLOW}Some components are not ready, recommended to investigate!${NC}"
    fi
}

# Add installation success message display function
show_success_message() {
    local host=$1
    local arch=$2

    echo -e "\n${GREEN}==================================================${NC}"
    echo -e "${GREEN}          EulerCopilot Deployment Completed!       ${NC}"
    echo -e "${GREEN}==================================================${NC}"

    echo -e "${YELLOW}Access Information:${NC}"
    echo -e "EulerCopilot UI:    ${eulercopilot_address}"
    echo -e "AuthHub Admin UI:   ${authhub_address}"

    echo -e "\n${YELLOW}System Information:${NC}"
    echo -e "Internal IP:    ${host}"
    echo -e "System Arch:    $(uname -m) (identified as: ${arch})"
    echo -e "Plugins Dir:    ${PLUGINS_DIR}"
    echo -e "Chart Dir:      ${DEPLOY_DIR}/chart/"

    echo -e "${BLUE}Operation Guide:${NC}"
    echo -e "1. Check cluster status: kubectl get pod -n $NAMESPACE"
    echo -e "2. View real-time logs: kubectl logs -f <POD_NAME> -n $NAMESPACE "
    echo -e "   Example: kubectl logs -f framework-deploy-5577c87b6-h82g8 -n euler-copilot"
    echo -e "3. Check POD status: kubectl get pods -n $NAMESPACE"


}

main "$@"
