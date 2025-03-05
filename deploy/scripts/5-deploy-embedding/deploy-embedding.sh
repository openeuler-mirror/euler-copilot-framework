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

check_service() {
    echo -e "${BLUE}步骤1/4：检查服务状态...${NC}"
    if ! systemctl is-active --quiet ollama; then
        echo -e "${RED}[ERROR] Ollama服务未运行${NC}"
        echo -e "${YELLOW}可能原因："
        echo "1. 服务未安装"
        echo "2. 系统未启用服务"
        echo -e "请先执行ollama-install.sh安装服务${NC}"
        exit 1
    fi
}

download_model() {
    echo -e "${BLUE}步骤2/4：下载模型文件...${NC}"
    if [[ -f "$MODEL_FILE" ]]; then
        echo -e "${GREEN}[SUCCESS] 模型文件已存在，跳过下载${NC}"
        return 0
    fi

    echo -e "${YELLOW}开始下载模型...${NC}"
    if ! wget --tries=3 --content-disposition -O "$MODEL_FILE" "$MODEL_URL"; then
        echo -e "${RED}[ERROR] 模型下载失败${NC}"
        echo -e "${YELLOW}可能原因："
        echo "1. URL已失效（当前URL: $MODEL_URL）"
        echo "2. 网络连接问题"
        echo -e "3. 磁盘空间不足（当前剩余：$(df -h . | awk 'NR==2 {print $4}')）${NC}"
        exit 1
    fi
    echo -e "${GREEN}[SUCCESS] 模型下载完成(文件大小：$(du -h $MODEL_FILE | awk '{print $1}' ${NC}))"
}

create_modelfile() {
    echo -e "${BLUE}步骤3/4：创建模型配置...${NC}"
    cat > "$MODELLEFILE" <<EOF
FROM ./$MODEL_FILE
PARAMETER num_ctx 4096
PARAMETER num_gpu 1
EOF
    echo -e "${GREEN}[SUCCESS] Modelfile创建成功${NC}"
}

create_model() {
    echo -e "${BLUE}步骤4/4：导入模型...${NC}"
    if ollama list | grep -q "$MODEL_NAME"; then
        echo -e "${GREEN}[SUCCESS] 模型已存在，跳过创建${NC}"
        return 0
    fi

    if ! ollama create "$MODEL_NAME" -f "$MODELLEFILE"; then
        echo -e "${RED}[ERROR] 模型创建失败${NC}"
        echo -e "${YELLOW}可能原因："
	echo "1. Modelfile格式错误 (当前路径：$(pwd)/$MODELLEFILE)"
	echo -e "2. 模型文件损坏 (MD5校验：$(md5sum $MODEL_FILE | awk '{print $1}' ${NC})"
        exit 1
    fi
    echo -e "${GREEN}[SUCCESS] 模型导入成功${NC}"
}

verify_deployment() {
    echo -e "${BLUE}验证部署结果...${NC}"
    local retries=3
    local wait_seconds=15
    local test_output=$(mktemp)
    local MAX_ATTEMPTS=5
    local INTERVAL=3
    local ATTEMPT=1

    # 基础验证
    if ! ollama list | grep -q "$MODEL_NAME"; then
        echo -e "${RED}[ERROR] 基础验证失败 - 未找到模型 $MODEL_NAME${NC}"
        echo -e "${YELLOW}排查建议："
        echo "1. 检查服务状态：systemctl status ollama"
        echo -e "2. 查看创建日志：journalctl -u ollama | tail -n 50${NC}"
        exit 1
    fi
    echo -e "${GREEN}[SUCCESS] 基础验证通过 - 检测到模型: $MODEL_NAME${NC}"

    # 增强验证：通过API获取嵌入向量
    echo -e "${YELLOW}执行API测试（超时时间${TIMEOUT_DURATION}秒）...${NC}"

    while [ $ATTEMPT -le $retries ]; do
        echo -e "${YELLOW}尝试 $ATTEMPT: 发送请求...${NC}"

        # 执行curl命令并将结果存储在变量中，同时不在控制台上打印
        RESPONSE=$(curl -k -X POST http://localhost:11434/v1/embeddings \
            -H "Content-Type: application/json" \
            -d '{"input": "The food was delicious and the waiter...", "model": "bge-m3", "encoding_format": "float"}' -s)

        # 检查响应是否为空
        if [[ -n "$RESPONSE" ]]; then
            # 如果需要保存响应到文件而不打印在控制台上，取消下面一行的注释
            # echo "$RESPONSE" > response.txt
            return 0 # 成功，无需打印响应
        else
            ((ATTEMPT++))
            if [ $ATTEMPT -le $retries ]; then
                sleep $INTERVAL
            else
                echo -e "${RED}[ERROR] 已达到最大尝试次数($retries)，仍未收到响应${NC}"
                return 1
            fi
        fi
    done
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
echo -e "${BLUE}=== 模型部署成功 ===${NC}"

cat << EOF
${GREEN}使用说明：${NC}
1. 启动交互模式：ollama run $MODEL_NAME
2. API访问示例：
curl -k -X POST http://localhost:11434/v1/embeddings \\
-H "Content-Type: application/json" \\
-d '{"input": "The food was delicious and the waiter...", "model": "bge-m3", "encoding_format": "float"}'
EOF
