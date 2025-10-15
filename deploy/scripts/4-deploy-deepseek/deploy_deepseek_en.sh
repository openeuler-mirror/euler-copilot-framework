#!/bin/bash
set -euo pipefail

# Color definitions
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # Reset color

# Configuration parameters
readonly MODEL_NAME="deepseek-llm-7b-chat"
readonly MODEL_URL="https://repo.oepkgs.net/openEuler/rpm/openEuler-22.03-LTS/contrib/eulercopilot/models/deepseek-llm-7b-chat-Q4_K_M.gguf"
readonly MODEL_FILE="deepseek-llm-7b-chat-Q4_K_M.gguf"
readonly MODEL_DIR="/home/eulercopilot/models"
readonly MODELLEFILE="Modelfile"
readonly TIMEOUT_DURATION=45

# Initialize working directory
readonly WORK_DIR=$(pwd)
mkdir -p "$MODEL_DIR"

check_service() {
    echo -e "${BLUE}Step 1/5: Checking service status...${NC}"
    if ! systemctl is-active --quiet ollama; then
        echo -e "${RED}Ollama service not running${NC}"
        echo -e "${YELLOW}Please run ollama-install.sh to install service first${NC}"
        exit 1
    fi
    echo -e "${GREEN}Service status normal${NC}"
}

check_network() {
    local url_to_check=$(echo "$MODEL_URL" | awk -F/ '{print $1 "//" $3}')
    echo -e "${BLUE}Step 2/5: Checking network connection...${NC}"
    if curl --silent --head --fail --max-time 5 "$url_to_check" >/dev/null 2>&1; then
        echo -e "${GREEN}Model repository accessible${NC}"
        return 0
    else
        echo -e "${RED}[ERROR] Unable to connect to model repository${NC}"
        return 1
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
        exit 1
    fi

    # Online download mode
    echo -e "${YELLOW}Starting online model download...${NC}"

    # Get expected file size
    EXPECTED_SIZE=$(curl -sLI "$MODEL_URL" | grep -i 'Content-Length' | awk '{print $2}' | tr -d '\r')
    EXPECTED_SIZE=${EXPECTED_SIZE:-0}

    # Start download process
    wget --tries=3 --content-disposition -O "$model_path" "$MODEL_URL" --progress=dot:binary >/dev/null 2>&1 &
    local wget_pid=$!

    # Show progress bar
    show_progress $wget_pid

    # Wait for download to complete
    if wait $wget_pid; then
        echo -e "\n${GREEN}[SUCCESS] Model download completed (file size: $(du -h "$model_path" | awk '{print $1}'))${NC}"
    else
        echo -e "\n${RED}[ERROR] Model download failed${NC}"
        echo -e "${YELLOW}Possible reasons:"
        echo "1. URL expired (current URL: $MODEL_URL)"
        echo "2. Network connection issue"
        echo -e "3. Insufficient disk space (current available: $(df -h ${MODEL_DIR} | awk 'NR==2 {print $4}'))${NC}"
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
    echo -e "${BLUE}Step 5/5: Verifying deployment result...${NC}"
    if ! command -v jq &> /dev/null; then
        echo -e "${YELLOW}Note: jq not installed, response parsing may be limited, recommend installing jq for better output.${NC}"
    fi

    local retries=3
    local interval=5
    local attempt=1

    if ! ollama list | grep -qw "${MODEL_NAME}"; then
        echo -e "${RED}Basic verification failed - model ${MODEL_NAME} not found${NC}"
        exit 1
    fi
    echo -e "${GREEN}Basic verification passed - detected model: ${MODEL_NAME}${NC}"

    echo -e "${YELLOW}Executing API test (timeout ${TIMEOUT_DURATION} seconds)...${NC}"

    while [ $attempt -le $retries ]; do
        echo -e "${BLUE}Attempt $attempt: Sending test request...${NC}"

        response=$(timeout ${TIMEOUT_DURATION} curl -s http://localhost:11434/v1/chat/completions \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer sk-123456" \
            -d '{
                "model": "'"${MODEL_NAME}"'",
                "messages": [
                    {"role": "system", "content": "You are an AI assistant"},
                    {"role": "user", "content": "Hello, please recite a Chinese ancient poem"}
                ],
                "stream": false
            }')

        if [[ $? -eq 0 ]] && [[ -n "$response" ]]; then
            echo -e "${GREEN}Test response successful, received valid output:"
            if jq -e .choices[0].message.content <<< "$response" &> /dev/null; then
                jq .choices[0].message.content <<< "$response"
            else
                echo "$response"
            fi
            return 0
        else
            echo -e "${YELLOW}Request did not receive valid response, retrying...${NC}"
            ((attempt++))
            sleep $interval
        fi
    done

    echo -e "${RED}Verification failed: No valid response received after ${retries} retries${NC}"
    return 1
}

### Main execution flow ###
echo -e "${BLUE}=== Starting Model Deployment ===${NC}"
{
    check_service
    handle_model
    create_modelfile
    create_model
    verify_deployment || true
}

echo -e "${GREEN}=== Model Deployment Successful ===${NC}"

echo -e "${YELLOW}Usage Instructions:${NC}"
echo -e "${YELLOW}1. Start interactive mode: ollama run $MODEL_NAME${NC}"
echo -e "${BLUE}2. API access example:${NC}"
cat << EOF
curl http://localhost:11434/v1/chat/completions \\
-H "Content-Type: application/json" \\
-H "Authorization: Bearer sk-123456" \\
-d '{
    "model": "$MODEL_NAME",
    "messages": [
        {"role": "system", "content": "You are an AI assistant"},
        {"role": "user", "content": "Hello"}
    ],
    "stream": false,
    "n": 1,
    "max_tokens": 2048
}'
EOF

echo -e "${BLUE}3. Streaming conversation mode:${NC}"
echo -e "${BLUE}Change "stream": false to "stream": true in the above request${NC}"
