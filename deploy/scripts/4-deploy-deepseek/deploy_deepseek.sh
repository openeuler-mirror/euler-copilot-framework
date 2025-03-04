#!/bin/bash
set -euo pipefail

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 重置颜色

# 配置参数
readonly MODEL_NAME="deepseek-llm-7b-chat"
readonly MODEL_URL="https://modelscope.cn/models/second-state/Deepseek-LLM-7B-Chat-GGUF/resolve/master/deepseek-llm-7b-chat-Q4_K_M.gguf"
readonly MODEL_FILE="deepseek-llm-7b-chat-Q4_K_M.gguf"
readonly MODELLEFILE="Modelfile"
readonly TIMEOUT_DURATION=45

check_service() {
    echo -e "${BLUE}步骤1/5：检查服务状态...${NC}"
    if ! systemctl is-active --quiet ollama; then
        echo -e "${RED}Ollama服务未运行${NC}"
        echo -e "${YELLOW}请先执行ollama-install.sh安装服务${NC}"
        exit 1
    fi
    echo -e "${GREEN}服务状态正常${NC}"
}

download_model() {
    echo -e "${BLUE}步骤2/5：下载模型文件...${NC}"
    if [[ -f "$MODEL_FILE" ]]; then
        echo -e "${GREEN}模型文件已存在，跳过下载${NC}"
        return 0
    fi

    echo -e "${YELLOW}开始下载模型...${NC}"
    
    # 检查下载工具
    local download_cmd
    if command -v wget &> /dev/null; then
        download_cmd="wget --tries=3 --content-disposition -O '$MODEL_FILE' '$MODEL_URL'"
    elif command -v curl &> /dev/null; then
        download_cmd="curl -# -L -o '$MODEL_FILE' '$MODEL_URL'"
    else
        echo -e "${RED}错误：需要wget或curl来下载模型文件${NC}"
        exit 1
    fi

    if ! eval "$download_cmd"; then
        echo -e "${RED}模型下载失败，删除不完整文件...${NC}"
        rm -f "$MODEL_FILE"
        exit 1
    fi
    
    echo -e "${GREEN}模型下载完成（文件大小：$(du -h $MODEL_FILE | cut -f1)）${NC}"
}

create_modelfile() {
    echo -e "${BLUE}步骤3/5：创建模型配置...${NC}"
    cat > "$MODELLEFILE" <<EOF
FROM ./$MODEL_FILE
PARAMETER num_ctx 4096
PARAMETER num_gpu 1
EOF
    echo -e "${GREEN}Modelfile创建成功${NC}"
}

create_model() {
    echo -e "${BLUE}步骤4/5：导入模型...${NC}"
    if ollama list | grep -qw "$MODEL_NAME"; then
        echo -e "${GREEN}模型已存在，跳过创建${NC}"
        return 0
    fi

    if ! ollama create "$MODEL_NAME" -f "$MODELLEFILE"; then
        echo -e "${RED}模型创建失败${NC}"
        echo -e "${YELLOW}可能原因："
        echo "1. Modelfile格式错误（当前路径：$(pwd)/$MODELLEFILE）"
        echo "2. 模型文件损坏（MD5校验：$(md5sum $MODEL_FILE | cut -d' ' -f1)）${NC}"
        exit 1
    fi
    echo -e "${GREEN}模型导入成功${NC}"
}

verify_deployment() {
    echo -e "${BLUE}步骤5/5：验证部署结果...${NC}"
    # 检查jq依赖
    if ! command -v jq &> /dev/null; then
        echo -e "${YELLOW}注意：jq未安装，响应解析可能受限，建议安装jq以获得更好的输出。${NC}"
    fi

    local retries=3
    local interval=5
    local attempt=1

    # 基础验证
    if ! ollama list | grep -qw "$MODEL_NAME"; then
        echo -e "${RED}基础验证失败 - 未找到模型 $MODEL_NAME${NC}"
        echo -e "${YELLOW}排查建议："
        echo "1. 检查服务状态：systemctl status ollama"
        echo "2. 查看创建日志：journalctl -u ollama | tail -n 50${NC}"
        exit 1
    fi
    echo -e "${GREEN}基础验证通过 - 检测到模型: $MODEL_NAME${NC}"

    # API功能验证
    echo -e "${YELLOW}执行API测试（超时时间${TIMEOUT_DURATION}秒）...${NC}"
    
    while [ $attempt -le $retries ]; do
        echo -e "${BLUE}尝试 $attempt: 发送测试请求...${NC}"
        response=$(timeout $TIMEOUT_DURATION curl -s -X POST http://localhost:11434/api/generate \
            -d "{\"model\": \"$MODEL_NAME\", \"prompt\": \"你好，请说一首中文古诗\", \"stream\": false}")

        if [[ $? -eq 0 ]] && [[ -n "$response" ]]; then
            echo -e "${GREEN}测试响应成功，收到有效输出："
            # 处理JSON解析
            if jq -e .response <<< "$response" &> /dev/null; then
                jq .response <<< "$response"
            else
                echo "$response"
            fi
            return 0
        else
            echo -e "${YELLOW}请求未得到有效响应${NC}"
            ((attempt++))
            sleep $interval
        fi
    done

    echo -e "${RED}验证失败：经过 $retries 次重试仍未收到有效响应${NC}"
    exit 1
}

### 主执行流程 ###
echo -e "${BLUE}=== 开始模型部署 ===${NC}"
{
    check_service
    download_model
    create_modelfile
    create_model
    verify_deployment
}
echo -e "${GREEN}=== 模型部署成功 ===${NC}"

cat << EOF
${YELLOW}使用说明：
1. 启动交互模式：ollama run $MODEL_NAME
2. API访问示例：
curl -X POST http://localhost:11434/api/generate \\
-d "{\\"model\\": \\"$MODEL_NAME\\", \\"prompt\\": \\"你好，介绍一下上海\\", \\"stream\\": false}"

3. 流式对话模式：
curl http://localhost:11434/api/chat \\
-d "{\\"model\\": \\"$MODEL_NAME\\", \\"messages\\": [{ \\"role\\": \\"user\\", \\"content\\": \\"你好\\" }]}"
EOF