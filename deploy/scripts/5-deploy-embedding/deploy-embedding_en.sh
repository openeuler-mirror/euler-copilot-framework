#!/bin/bash
set -euo pipefail

# Color definitions
RED='\e[31m'
GREEN='\e[32m'
YELLOW='\e[33m'
BLUE='\e[34m'
NC='\e[0m' # Reset color

# Configuration parameters
readonly MODEL_NAME="bge-m3"
readonly MODEL_URL="https://modelscope.cn/models/gpustack/bge-m3-GGUF/resolve/master/bge-m3-Q4_K_M.gguf"
readonly MODEL_FILE="bge-m3-Q4_K_M.gguf"
readonly MODELLEFILE="Modelfile"
readonly TIMEOUT_DURATION=45
readonly MODEL_DIR="/home/eulercopilot/models"

# Initialize working directory
readonly WORK_DIR=$(pwd)
mkdir -p "$MODEL_DIR"

# Network check function (unchanged)
check_network() {
    echo -e "${BLUE}Step 1/5: Checking network connection...${NC}"
    local test_url="https://modelscope.cn"
    if curl --silent --head --fail --max-time 5 "$test_url" >/dev/null 2>&1; then
        echo -e "${GREEN}[SUCCESS] Network connection normal${NC}"
        return 0
    else
        echo -e "${YELLOW}[WARNING] Unable to connect to network, switching to offline mode${NC}"
        return 1
    fi
}

# Service check (unchanged)
check_service() {
    echo -e "${BLUE}Step 2/5: Checking service status...${NC}"
    if ! systemctl is-active --quiet ollama; then
        echo -e "${RED}[ERROR] Ollama service not running${NC}"
        echo -e "${YELLOW}Possible reasons:"
        echo "1. Service not installed"
        echo "2. System service not enabled"
        echo -e "Please run ollama-install.sh to install service first${NC}"
        exit 1
    fi
}

show_progress() {
    local pid=$1
    local cols=$(tput cols)
    local bar_width=$((cols - 20))

    while kill -0 "$pid" 2>/dev/null; do
        local current_size=$(du -b "${MODEL_DIR}/${MODEL_FILE}" 2>/dev/null | awk '{print $1}')
        local percent=$((current_size * 100 / EXPECTED_SIZE))
        [ $percent -gt 100 ] && percent=100

        local filled=$((percent * bar_width / 100))
        local empty=$((bar_width - filled))

        printf "\r[%-*s] %3d%%" "$bar_width" "$(printf '%0.s=' {1..$filled})$(printf '%0.s ' {1..$empty})" "$percent"
        sleep 1
    done
}

detect_gpu() {
    echo -e "${BLUE}Detecting GPU devices...${NC}"

    # Check if NVIDIA GPU hardware exists
    if lspci | grep -i nvidia || [ -c /dev/nvidia0 ]; then
        echo -e "${GREEN}Detected NVIDIA GPU device${NC}"

        # Check if NVIDIA driver is installed
        if command -v nvidia-smi &> /dev/null; then
            echo -e "${GREEN}NVIDIA driver installed${NC}"
            return 0
        else
            echo -e "${YELLOW}GPU detected but NVIDIA driver not installed, will use CPU mode${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}No GPU device detected, will use CPU mode${NC}"
        return 1
    fi
}

handle_model() {
    echo -e "${BLUE}Step 3/5: Processing model file...${NC}"
    local model_path="${MODEL_DIR}/${MODEL_FILE}"

    # Check local model
    if [[ -f "$model_path" ]]; then
        echo -e "${GREEN}Detected local model file ${model_path}${NC}"
        return 0
    fi

    # Check network when download is needed
    if ! check_network; then
        echo -e "${RED}[ERROR] Unable to download model: network connection unavailable${NC}"
        echo -e "${YELLOW}Solutions:"
        echo -e "1. Please check network connection"
        echo -e "2. You can manually place model file at: ${MODEL_DIR}"
        exit 1
    fi

    # Online download mode
    echo -e "${YELLOW}Starting online model download...${NC}"
    echo -e "${YELLOW}Download URL: ${MODEL_URL}${NC}"

    # Create temporary file to record wget output
    local wget_output=$(mktemp)

    # Execute download and show dynamic progress bar
    (
        wget --tries=3 --content-disposition -O "$model_path" "$MODEL_URL" --progress=dot:binary 2>&1 | \
        while IFS= read -r line; do
            # Extract percentage
            if [[ "$line" =~ ([0-9]{1,3})% ]]; then
                local percent=${BASH_REMATCH[1]}
                # Calculate progress bar length (based on terminal width - 20)
                local cols=$(tput cols)
                local bar_width=$((cols - 20))
                local filled=$((percent * bar_width / 100))
                local empty=$((bar_width - filled))

                # Build progress bar
                local progress_bar=$(printf "%${filled}s" | tr ' ' '=')
                local remaining_bar=$(printf "%${empty}s" | tr ' ' ' ')

                # Show progress (use carriage return to overwrite)
                printf "\r[%s%s] %3d%%" "$progress_bar" "$remaining_bar" "$percent"
            fi
        done
        echo  # New line
    ) | tee "$wget_output"

    # Check download result
    if grep -q "100%" "$wget_output"; then
        echo -e "${GREEN}[SUCCESS] Model download completed (file size: $(du -h "$model_path" | awk '{print $1}'))${NC}"
        echo -e "${GREEN}Storage path: ${model_path}${NC}"
        rm -f "$wget_output"
    else
        echo -e "${RED}[ERROR] Model download failed${NC}"
        echo -e "${YELLOW}Possible reasons:"
        echo "1. URL expired (current URL: $MODEL_URL)"
        echo "2. Network connection issue"
        echo -e "3. Insufficient disk space (current available: $(df -h ${MODEL_DIR} | awk 'NR==2 {print $4}'))${NC}"
        rm -f "$wget_output"
        exit 1
    fi
}

create_modelfile() {
    echo -e "${BLUE}Step 4/5: Creating model configuration...${NC}"

    # GPU parameter configuration
    local gpu_param=""
    if detect_gpu; then
        gpu_param="PARAMETER num_gpu -1"
        echo -e "${GREEN}GPU acceleration mode enabled${NC}"
    else
        echo -e "${YELLOW}Using CPU mode${NC}"
        gpu_param="PARAMETER num_gpu 0"
    fi

    cat > "${WORK_DIR}/${MODELLEFILE}" <<EOF
FROM ${MODEL_DIR}/${MODEL_FILE}
PARAMETER num_ctx 4096
${gpu_param}
EOF

    echo -e "${GREEN}Modelfile created successfully (path: ${WORK_DIR}/${MODELLEFILE})${NC}"
    echo -e "${YELLOW}Generated Modelfile content:${NC}"
    cat "${WORK_DIR}/${MODELLEFILE}"
}

create_model() {
    echo -e "${BLUE}Step 5/5: Importing model...${NC}"
    if ollama list | grep -qw "${MODEL_NAME}"; then
        echo -e "${GREEN}Model already exists, skipping creation${NC}"
        return 0
    fi

    if ! ollama create "${MODEL_NAME}" -f "${WORK_DIR}/${MODELLEFILE}"; then
        echo -e "${RED}Model creation failed${NC}"
        echo -e "${YELLOW}Possible reasons:"
        echo "1. Modelfile format error (path: ${WORK_DIR}/${MODELLEFILE})"
        echo "2. Model file corrupted (MD5 checksum: $(md5sum "${MODEL_DIR}/${MODEL_FILE}" | cut -d' ' -f1))"
        exit 1
    fi
    echo -e "${GREEN}Model imported successfully${NC}"
}

verify_deployment() {
    echo -e "${BLUE}Verifying deployment result...${NC}"
    local retries=3
    local wait_seconds=15
    local test_output=$(mktemp)
    local INTERVAL=5

    # Basic verification
    if ! ollama list | grep -q "${MODEL_NAME}"; then
        echo -e "${RED}[ERROR] Basic verification failed - model ${MODEL_NAME} not found${NC}"
        echo -e "${YELLOW}Troubleshooting suggestions:"
        echo "1. Check service status: systemctl status ollama"
        echo -e "2. View creation logs: journalctl -u ollama | tail -n 50${NC}"
        exit 1
    fi

    # Enhanced verification: Get embeddings via API
    echo -e "${YELLOW}Executing API test (maximum ${retries} attempts)...${NC}"
    for ((i=1; i<=retries; i++)); do
        local http_code=$(curl -k -o /dev/null -w "%{http_code}" -X POST http://localhost:11434/v1/embeddings \
            -H "Content-Type: application/json" \
            -d '{"input": "The food was delicious and the waiter...", "model": "bge-m3", "encoding_format": "float"}' -s -m $TIMEOUT_DURATION)

        if [[ "$http_code" == "200" ]]; then
            echo -e "${GREEN}[SUCCESS] API test successful (HTTP status code: 200)${NC}"
            return 0
        else
            echo -e "${YELLOW}[WARNING] Attempt ${i} failed (HTTP status code: ${http_code})${NC}"
            sleep $INTERVAL
        fi
    done

    echo -e "${RED}[ERROR] API test failed, reached maximum attempts${NC}"
    echo -e "${YELLOW}Possible reasons:"
    echo "1. Model not loaded correctly"
    echo "2. Service response timeout (current timeout setting: ${TIMEOUT_DURATION} seconds)"
    echo -e "3. Insufficient system resources (check GPU memory usage)${NC}"
    exit 1
}

### Main execution flow ###
echo -e "${BLUE}=== Starting Model Deployment ===${NC}"
{
    check_service
    handle_model
    create_modelfile
    create_model
    verify_deployment
}
echo -e "${BLUE}=== Model Deployment Successful ===${NC}"
cat << EOF
${GREEN}Usage Instructions:${NC}
1. Start interactive mode: ollama run $MODEL_NAME
2. API access example:
curl -k -X POST http://localhost:11434/v1/embeddings \\
-H "Content-Type: application/json" \\
-d '{"input": "The food was delicious and the waiter...", "model": "bge-m3", "encoding_format": "float"}'
EOF
