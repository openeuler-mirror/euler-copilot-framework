#!/bin/bash
set -euo pipefail

# 颜色定义
RED='\e[31m'
GREEN='\e[32m'
YELLOW='\e[33m'
BLUE='\e[34m'
NC='\e[0m' # 重置颜色

# 配置参数
readonly MODEL_NAME="bge-m3"
readonly MODEL_URL="https://modelscope.cn/models/gpustack/bge-m3-GGUF/resolve/master/bge-m3-Q4_K_M.gguf"
readonly MODEL_FILE="bge-m3-Q4_K_M.gguf"
readonly MODELLEFILE="Modelfile"
readonly TIMEOUT_DURATION=45
readonly MODEL_DIR="/home/eulercopilot/models"

# 初始化工作目录
readonly WORK_DIR=$(pwd)
mkdir -p "$MODEL_DIR"

# 网络检查函数（保持不变）
check_network() {
    echo -e "${BLUE}步骤1/5：检查网络连接...${NC}"
    local test_url="https://modelscope.cn"
    if curl --silent --head --fail --max-time 5 "$test_url" >/dev/null 2>&1; then
        echo -e "${GREEN}[SUCCESS] 网络连接正常${NC}"
        return 0
    else
        echo -e "${YELLOW}[WARNING] 无法连接网络，切换到离线模式${NC}"
        return 1
    fi
}

# 服务检查（保持不变）
check_service() {
    echo -e "${BLUE}步骤2/5：检查服务状态...${NC}"
    if ! systemctl is-active --quiet ollama; then
        echo -e "${RED}[ERROR] Ollama服务未运行${NC}"
        echo -e "${YELLOW}可能原因："
        echo "1. 服务未安装"
        echo "2. 系统未启用服务"
        echo -e "请先执行ollama-install.sh安装服务${NC}"
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
    echo -e "${BLUE}检测GPU设备...${NC}"

    # 检查是否存在NVIDIA GPU硬件
    if lspci | grep -i nvidia || [ -c /dev/nvidia0 ]; then
        echo -e "${GREEN}检测到NVIDIA GPU设备${NC}"

        # 检查NVIDIA驱动是否安装
        if command -v nvidia-smi &> /dev/null; then
            echo -e "${GREEN}NVIDIA驱动已安装${NC}"
            return 0
        else
            echo -e "${YELLOW}检测到GPU但未安装NVIDIA驱动，将使用CPU模式${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}未检测到GPU设备，将使用CPU模式${NC}"
        return 1
    fi
}

handle_model() {
    echo -e "${BLUE}步骤3/5：处理模型文件...${NC}"
    local model_path="${MODEL_DIR}/${MODEL_FILE}"

    # 检查本地模型
    if [[ -f "$model_path" ]]; then
        echo -e "${GREEN}检测到本地模型文件 ${model_path}${NC}"
        return 0
    fi

    # 需要下载时检查网络
    if ! check_network; then
        echo -e "${RED}[ERROR] 无法下载模型：网络连接不可用${NC}"
	echo -e "${YELLOW}解决方案："
        echo -e "1. 请检查网络连接"
        echo -e "2. 可以手动将模型文件放置到：${MODEL_DIR}"
        exit 1
    fi

    # 在线下载模式
    echo -e "${YELLOW}开始在线下载模型...${NC}"
    echo -e "${YELLOW}下载地址：${MODEL_URL}${NC}"
    

    # 创建临时文件记录wget输出
    local wget_output=$(mktemp)

    # 执行下载并显示动态进度条
    (
        wget --tries=3 --content-disposition -O "$model_path" "$MODEL_URL" --progress=dot:binary 2>&1 | \
        while IFS= read -r line; do
            # 提取百分比
            if [[ "$line" =~ ([0-9]{1,3})% ]]; then
                local percent=${BASH_REMATCH[1]}
                # 计算进度条长度（基于终端宽度-20）
                local cols=$(tput cols)
                local bar_width=$((cols - 20))
                local filled=$((percent * bar_width / 100))
                local empty=$((bar_width - filled))

                # 构建进度条
                local progress_bar=$(printf "%${filled}s" | tr ' ' '=')
                local remaining_bar=$(printf "%${empty}s" | tr ' ' ' ')

                # 显示进度（使用回车覆盖）
                printf "\r[%s%s] %3d%%" "$progress_bar" "$remaining_bar" "$percent"
            fi
        done
        echo  # 换行
    ) | tee "$wget_output"

    # 检查下载结果
    if grep -q "100%" "$wget_output"; then
        echo -e "${GREEN}[SUCCESS] 模型下载完成（文件大小：$(du -h "$model_path" | awk '{print $1}')）${NC}"
	echo -e "${GREEN}存储路径：${model_path}${NC}"
        rm -f "$wget_output"
    else
        echo -e "${RED}[ERROR] 模型下载失败${NC}"
        echo -e "${YELLOW}可能原因："
        echo "1. URL已失效（当前URL: $MODEL_URL）"
        echo "2. 网络连接问题"
        echo -e "3. 磁盘空间不足（当前剩余：$(df -h ${MODEL_DIR} | awk 'NR==2 {print $4}')）${NC}"
        rm -f "$wget_output"
        exit 1
    fi

}

create_modelfile() {
    echo -e "${BLUE}步骤4/5：创建模型配置...${NC}"
    
    # GPU参数配置
    local gpu_param=""
    if detect_gpu; then
        gpu_param="PARAMETER num_gpu -1"
        echo -e "${GREEN}已启用GPU加速模式${NC}"
    else
        echo -e "${YELLOW}使用CPU模式运行${NC}"
	gpu_param="PARAMETER num_gpu 0"
    fi

    cat > "${WORK_DIR}/${MODELLEFILE}" <<EOF
FROM ${MODEL_DIR}/${MODEL_FILE}
PARAMETER num_ctx 4096
${gpu_param}
EOF

    echo -e "${GREEN}Modelfile创建成功（路径：${WORK_DIR}/${MODELLEFILE}）${NC}"
    echo -e "${YELLOW}生成的Modelfile内容：${NC}"
    cat "${WORK_DIR}/${MODELLEFILE}"
}

create_model() {
    echo -e "${BLUE}步骤5/5：导入模型...${NC}"
    if ollama list | grep -qw "${MODEL_NAME}"; then
        echo -e "${GREEN}模型已存在，跳过创建${NC}"
        return 0
    fi

    if ! ollama create "${MODEL_NAME}" -f "${WORK_DIR}/${MODELLEFILE}"; then
        echo -e "${RED}模型创建失败${NC}"
        echo -e "${YELLOW}可能原因："
        echo "1. Modelfile格式错误（路径：${WORK_DIR}/${MODELLEFILE}）"
        echo "2. 模型文件损坏（MD5校验：$(md5sum "${MODEL_DIR}/${MODEL_FILE}" | cut -d' ' -f1)）"
        exit 1
    fi
    echo -e "${GREEN}模型导入成功${NC}"
}

verify_deployment() {
    echo -e "${BLUE}验证部署结果...${NC}"
    local retries=3
    local wait_seconds=15
    local test_output=$(mktemp)
    local INTERVAL=5

    # 基础验证
    if ! ollama list | grep -q "${MODEL_NAME}"; then
        echo -e "${RED}[ERROR] 基础验证失败 - 未找到模型 ${MODEL_NAME}${NC}"
        echo -e "${YELLOW}排查建议："
        echo "1. 检查服务状态：systemctl status ollama"
        echo -e "2. 查看创建日志：journalctl -u ollama | tail -n 50${NC}"
        exit 1
    fi

    # 增强验证：通过API获取嵌入向量
    echo -e "${YELLOW}执行API测试（最多尝试${retries}次）...${NC}"
    for ((i=1; i<=retries; i++)); do
        local http_code=$(curl -k -o /dev/null -w "%{http_code}" -X POST http://localhost:11434/v1/embeddings \
            -H "Content-Type: application/json" \
            -d '{"input": "The food was delicious and the waiter...", "model": "bge-m3", "encoding_format": "float"}' -s -m $TIMEOUT_DURATION)

        if [[ "$http_code" == "200" ]]; then
            echo -e "${GREEN}[SUCCESS] API测试成功（HTTP状态码：200）${NC}"
            return 0
        else
            echo -e "${YELLOW}[WARNING] 第${i}次尝试失败（HTTP状态码：${http_code}）${NC}"
            sleep $INTERVAL
        fi
    done

    echo -e "${RED}[ERROR] API测试失败，已达到最大尝试次数${NC}"
    echo -e "${YELLOW}可能原因："
    echo "1. 模型未正确加载"
    echo "2. 服务响应超时（当前超时设置：${TIMEOUT_DURATION}秒）"
    echo -e "3. 系统资源不足（检查GPU内存使用情况）${NC}"
    exit 1
}

### 主执行流程 ###
echo -e "${BLUE}=== 开始模型部署 ===${NC}"
{
    check_service
    handle_model
    create_modelfile
    create_model
    verify_deployment
}
echo -e "${BLUE}=== 模型部署成功 ===${NC}"
cat << EOF
${GREEN}使用说明：${NC}
1. 启动交互模式：ollama run $MODEL_NAME
2. API访问示例：
curl -k -X POST http://localhost:11434/v1/embeddings \\
-H "Content-Type: application/json" \\
-d '{"input": "The food was delicious and the waiter...", "model": "bge-m3", "encoding_format": "float"}'
EOF
