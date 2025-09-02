# 支持百川、chatglm、星火等AI大模型的容器化封装

已配好相关依赖，分为CPU和GPU版本，降低使用门槛，开箱即用。

## 拉取镜像(CPU版本)

```bash
docker pull openeuler/llm-server:1.0.0-oe2203sp3
```

## 拉取镜像(GPU版本)

```bash
docker pull icewangds/llm-server:1.0.0
```

## 下载模型, 并转换为gguf格式

```bash
# 安装huggingface
pip install huggingface-hub

# 下载你想要部署的模型
export HF_ENDPOINT=https://hf-mirror.com
huggingface-cli download --resume-download baichuan-inc/Baichuan2-13B-Chat --local-dir /root/models/Baichuan2-13B-Chat --local-dir-use-symlinks False

# gguf格式转换
cd /root/models/
git clone https://github.com/ggerganov/llama.cpp.git
python llama.cpp/convert-hf-to-gguf.py ./Baichuan2-13B-Chat
# 生成的gguf格式的模型路径 /root/models/Baichuan2-13B-Chat/ggml-model-f16.gguf
```

## 启动方式

需要Docker v25.0.0及以上版本。

若使用GPU镜像，需要OS上安装nvidia-container-toolkit，安装方式见<https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html>。

docker-compose.yaml:

```yaml
version: '3'
services:
  model:
    image: <image>:<tag>   #镜像名称与tag
    restart: on-failure:5
    ports:
      - 8001:8000    #监听端口号，修改“8001”以更换端口
    volumes:
      - /root/models:/models  # 大模型挂载目录
    environment:
      - MODEL=/models/Baichuan2-13B-Chat/ggml-model-f16.gguf  # 容器内的模型文件路径
      - MODEL_NAME=baichuan13b  # 自定义模型名称
      - KEY=sk-12345678  # 自定义API Key
      - CONTEXT=8192  # 上下文大小
      - THREADS=8    # CPU线程数，仅CPU部署时需要
    deploy: # 指定GPU资源, 仅GPU部署时需要
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

```bash
docker-compose -f docker-compose.yaml up
```

docker run:

```text
cpu部署: docker run -d --restart on-failure:5 -p 8001:8000 -v /root/models:/models -e MODEL=/models/Baichuan2-13B-Chat/ggml-model-f16.gguf -e MODEL_NAME=baichuan13b -e KEY=sk-12345678 openeuler/llm-server:1.0.0-oe2203sp3

gpu部署: docker run -d --gpus all --restart on-failure:5 -p 8001:8000 -v /root/models:/models -e MODEL=/models/Baichuan2-13B-Chat/ggml-model-f16.gguf -e MODEL_NAME=baichuan13b -e KEY=sk-12345678 icewangds/llm-server:1.0.0
```

## 成功部署验证

调用大模型接口测试，成功返回则表示大模型服务已部署成功

```bash
curl -X POST http://127.0.0.1:8001/v1/chat/completions \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer sk-12345678" \
     -d '{
           "model": "baichuan13b",
           "messages": [
             {"role": "system", "content": "你是一个社区助手，请回答以下问题。"},
             {"role": "user", "content": "你是谁?"}
           ],
           "stream": false,
           "max_tokens": 1024
         }'
```
