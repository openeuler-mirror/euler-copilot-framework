#!/bin/bash

# Enhanced color definitions
RESET='\033[0m'
BOLD='\033[1m'
RED='\033[38;5;196m'
GREEN='\033[38;5;46m'
YELLOW='\033[38;5;226m'
BLUE='\033[38;5;45m'
MAGENTA='\033[38;5;201m'
CYAN='\033[38;5;51m'
WHITE='\033[38;5;255m'
BG_RED='\033[48;5;196m'
BG_GREEN='\033[48;5;46m'
BG_BLUE='\033[48;5;45m'
DIM='\033[2m'

# Progress bar width
PROGRESS_WIDTH=50
NAMESPACE="euler-copilot"
TIMEOUT=300   # Max wait time (seconds)
INTERVAL=10   # Check interval (seconds)

# Global variables
authhub_address=""
eulercopilot_address=""

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --eulercopilot_address)
                if [ -n "$2" ]; then
                    eulercopilot_address="$2"
                    shift 2
                else
                    echo -e "${RED}Error: --eulercopilot_address requires a value${RESET}" >&2
                    exit 1
                fi
                ;;
            --authhub_address)
                if [ -n "$2" ]; then
                    authhub_address="$2"
                    shift 2
                else
                    echo -e "${RED}Error: --authhub_address requires a value${RESET}" >&2
                    exit 1
                fi
                ;;
            *)
                echo -e "${RED}Unknown option: $1${RESET}" >&2
                exit 1
                ;;
        esac
    done
}

# Prompt user for required parameters
prompt_for_addresses() {
    # If eulercopilot_address not provided via command line, prompt user
    if [ -z "$eulercopilot_address" ]; then
        echo -e "${YELLOW}EulerCopilot address not provided${RESET}"
        read -p "$(echo -e "${CYAN}Enter EulerCopilot address (e.g., http://myhost:30080): ${RESET}")" eulercopilot_address

        # Validate input not empty
        while [ -z "$eulercopilot_address" ]; do
            echo -e "${RED}Error: EulerCopilot address cannot be empty${RESET}"
            read -p "$(echo -e "${CYAN}Enter EulerCopilot address (e.g., http://myhost:30080): ${RESET}")" eulercopilot_address
        done
    fi

    # If authhub_address not provided via command line, prompt user
    if [ -z "$authhub_address" ]; then
        echo -e "${YELLOW}Authhub address not provided${RESET}"
        read -p "$(echo -e "${CYAN}Enter Authhub address (e.g., http://myhost:30081): ${RESET}")" authhub_address

        # Validate input not empty
        while [ -z "$authhub_address" ]; do
            echo -e "${RED}Error: Authhub address cannot be empty${RESET}"
            read -p "$(echo -e "${CYAN}Enter Authhub address (e.g., http://myhost:30081): ${RESET}")" authhub_address
        done
    fi
}

# Colorful progress bar function
colorful_progress() {
    local current=$1
    local total=$2
    local progress=$((current*100/total))
    local completed=$((PROGRESS_WIDTH*current/total))
    local remaining=$((PROGRESS_WIDTH-completed))

    printf "\r${BOLD}${BLUE}⟦${RESET}"
    printf "${BG_BLUE}${WHITE}%${completed}s${RESET}" | tr ' ' '▌'
    printf "${DIM}${BLUE}%${remaining}s${RESET}" | tr ' ' '·'
    printf "${BOLD}${BLUE}⟧${RESET} ${GREEN}%3d%%${RESET} ${CYAN}[%d/%d]${RESET}" \
        $progress $current $total
}

# Print separator line
print_separator() {
    echo -e "${BLUE}${BOLD}$(printf '━%.0s' $(seq 1 $(tput cols)))${RESET}"
}

# Print step title
print_step_title() {
    echo -e "\n${BG_BLUE}${WHITE}${BOLD} Step $1  ${RESET} ${MAGENTA}${BOLD}$2${RESET}"
    echo -e "${DIM}${BLUE}$(printf '━%.0s' $(seq 1 $(tput cols)))${RESET}"
}

# Get main script absolute path and switch to its directory
MAIN_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$MAIN_DIR" || exit 1

run_script_with_check() {
    local script_path=$1
    local script_name=$2
    local step_number=$3
    local auto_input=${4:-false}
    shift 4
    local extra_args=("$@")  # Use array for extra parameters

    # Pre-check: script exists
    if [ ! -f "$script_path" ]; then
        echo -e "\n${BOLD}${RED}✗ Fatal error:${RESET}${YELLOW}${script_name}${RESET}${RED} not found (path: ${CYAN}${script_path}${RED})${RESET}" >&2
        exit 1
    fi

    print_step_title $step_number "$script_name"

    # Get absolute path and execution directory
    local script_abs_path=$(realpath "$script_path")
    local script_dir=$(dirname "$script_abs_path")
    local script_base=$(basename "$script_abs_path")

    echo -e "${DIM}${BLUE}🠖 Script path: ${YELLOW}${script_abs_path}${RESET}"
    echo -e "${DIM}${BLUE}🠖 Working directory: ${YELLOW}${script_dir}${RESET}"
    echo -e "${DIM}${BLUE}🠖 Extra args: ${YELLOW}${extra_args[*]}${RESET}"
    echo -e "${DIM}${BLUE}🠖 Start time: ${YELLOW}$(date +'%Y-%m-%d %H:%M:%S')${RESET}"

    # Create temporary log file
    local log_file=$(mktemp)
    echo -e "${DIM}${BLUE}🠖 Temp log: ${YELLOW}${log_file}${RESET}"

    # Execute script (with auto-input and real-time logging)
    local exit_code=0
    if $auto_input; then
        (cd "$script_dir" && yes "" | bash "./$script_base" "${extra_args[@]}" 2>&1 | tee "$log_file")
    else
        (cd "$script_dir" && bash "./$script_base" "${extra_args[@]}" 2>&1 | tee "$log_file")
    fi
    exit_code=${PIPESTATUS[0]}

    # Handle execution result
    if [ $exit_code -eq 0 ]; then
        echo -e "\n${BOLD}${GREEN}✓ ${script_name} executed successfully!${RESET}"
        echo -e "${DIM}${CYAN}$(printf '%.0s─' $(seq 1 $(tput cols)))${RESET}"
        echo -e "${DIM}${CYAN}Operation log:${RESET}"
        cat "$log_file" | sed -e "s/^/${DIM}${CYAN}  🠖 ${RESET}/"
        echo -e "${DIM}${CYAN}$(printf '%.0s─' $(seq 1 $(tput cols)))${RESET}"
    else
        echo -e "\n${BOLD}${RED}✗ ${script_name} execution failed!${RESET}" >&2
        echo -e "${DIM}${RED}$(printf '%.0s─' $(seq 1 $(tput cols)))${RESET}" >&2
        echo -e "${DIM}${RED}Error log:${RESET}" >&2
        cat "$log_file" | sed -e "s/^/${DIM}${RED}  ✗ ${RESET}/" >&2
        echo -e "${DIM}${RED}$(printf '%.0s─' $(seq 1 $(tput cols)))${RESET}" >&2
        rm "$log_file"
        exit 1
    fi

    rm "$log_file"
    return $exit_code
}

# Uninstall all components
uninstall_all() {
    echo -e "\n${CYAN}▸ Uninstalling all Helm Releases...${RESET}"
    local RELEASES
    RELEASES=$(helm list -n $NAMESPACE --short 2>/dev/null || true)

    if [ -n "$RELEASES" ]; then
        echo -e "${YELLOW}Found Helm Releases:${RESET}"
        echo "$RELEASES" | awk '{print "  ➤ "$0}'
        for release in $RELEASES; do
            echo -e "${BLUE}Deleting: ${release}${RESET}"
            helm uninstall "$release" -n $NAMESPACE || echo -e "${RED}Delete failed, continuing...${RESET}"
        done
    else
        echo -e "${YELLOW}No Helm Releases to clean${RESET}"
    fi

    echo -e "\n${CYAN}▸ Cleaning persistent storage...${RESET}"
    local pvc_list
    pvc_list=$(kubectl get pvc -n $NAMESPACE -o name 2>/dev/null || true)

    if [ -n "$pvc_list" ]; then
        echo -e "${YELLOW}Found PVC resources:${RESET}"
        echo "$pvc_list" | awk '{print "  ➤ "$0}'
        echo "$pvc_list" | xargs -n 1 kubectl delete -n $NAMESPACE || echo -e "${RED}Delete failed, continuing...${RESET}"
    else
        echo -e "${YELLOW}No PVCs to clean${RESET}"
    fi

    echo -e "\n${CYAN}▸ Cleaning Secret resources...${RESET}"
    local secret_list
    secret_list=$(kubectl get secret -n $NAMESPACE -o name 2>/dev/null || true)

    if [ -n "$secret_list" ]; then
        echo -e "${YELLOW}Found Secret resources:${RESET}"
        echo "$secret_list" | awk '{print "  ➤ "$0}'
        echo "$secret_list" | xargs -n 1 kubectl delete -n $NAMESPACE || echo -e "${RED}Delete failed, continuing...${RESET}"
    else
        echo -e "${YELLOW}No Secrets to clean${RESET}"
    fi

    echo -e "\n${BG_GREEN}${WHITE}${BOLD} ✓ Complete ${RESET} ${GREEN}All resources cleaned${RESET}"
}

# Main header display
show_header() {
    clear
    echo -e "\n${BOLD}${MAGENTA}$(printf '✧%.0s' $(seq 1 $(tput cols)))${RESET}"
    echo -e "${BOLD}${WHITE}                  Euler Copilot One-Click Deployment System                  ${RESET}"
    echo -e "${BOLD}${MAGENTA}$(printf '✧%.0s' $(seq 1 $(tput cols)))${RESET}"
    echo -e "${CYAN}◈ Main directory: ${YELLOW}${MAIN_DIR}${RESET}"
    echo -e "${CYAN}◈ EulerCopilot address: ${YELLOW}${eulercopilot_address:-Not set}${RESET}"
    echo -e "${CYAN}◈ Authhub address: ${YELLOW}${authhub_address:-Not set}${RESET}\n"
}

# Modified start_deployment function step configuration
start_deployment() {
    local total_steps=8
    local current_step=1

    # Step configuration (script_path script_name auto_input extra_args_array)
    local steps=(
        "../1-check-env/check_env.sh Environment check false"
        "_conditional_tools_step Basic tools installation(k3s+helm) true"
        "../3-install-ollama/install_ollama.sh Ollama deployment true"
        "../4-deploy-deepseek/deploy_deepseek.sh Deepseek model deployment false"
        "../5-deploy-embedding/deploy-embedding.sh Embedding service deployment false"
        "../6-install-databases/install_databases.sh Database cluster deployment false"
        "../7-install-authhub/install_authhub.sh Authhub deployment true --authhub_address ${authhub_address}"
        "_conditional_eulercopilot_step EulerCopilot deployment true"
    )

    for step in "${steps[@]}"; do
        local script_path=$(echo "$step" | awk '{print $1}')
        local script_name=$(echo "$step" | awk '{print $2}')
        local auto_input=$(echo "$step" | awk '{print $3}')
        local extra_args=$(echo "$step" | awk '{for(i=4;i<=NF;i++) printf $i" "}')

        # Special step handling
        if [[ "$script_path" == "_conditional_tools_step" ]]; then
            handle_tools_step $current_step
        elif [[ "$script_path" == "_conditional_eulercopilot_step" ]]; then
            sleep 60
            handle_eulercopilot_step $current_step
        else
            run_script_with_check "$script_path" "$script_name" $current_step $auto_input $extra_args
        fi

        colorful_progress $current_step $total_steps
        ((current_step++))
    done
}

# Handle tools installation step
handle_tools_step() {
    local current_step=$1
    if command -v k3s >/dev/null 2>&1 && command -v helm >/dev/null 2>&1; then
        echo -e "${CYAN}🠖 k3s and helm detected, performing environment cleanup...${RESET}"
        uninstall_all
    else
        run_script_with_check "../2-install-tools/install_tools.sh" "Basic tools installation" $current_step true
    fi
}

handle_eulercopilot_step() {
    local current_step=$1
    local extra_args=()

    # Build extra arguments array
    [ -n "$authhub_address" ] && extra_args+=(--authhub_address "$authhub_address")
    [ -n "$eulercopilot_address" ] && extra_args+=(--eulercopilot_address "$eulercopilot_address")

    run_script_with_check "../8-install-EulerCopilot/install_eulercopilot.sh" "EulerCopilot deployment" $current_step true "${extra_args[@]}"
}

# Main execution flow
parse_arguments "$@"
prompt_for_addresses
show_header
start_deployment
