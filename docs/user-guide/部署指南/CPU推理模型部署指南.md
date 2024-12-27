# CPU推理模型部署指南

## 介绍

sysInfer是一款基于鲲鹏+openEuler的大模型推理加速框架，主要采用通用算力CPU作为部署主体，目前支持使用Baichuan系列和Llama3系列的权重进行加速推理，支持使用gguf的量化格式模型。作为CPU的推理框架，突破了传统GPU部署大模型推理的限制，采用点到点的推理部署策略，充分挖掘通用算力的潜能，显著提升了CPU在大模型推理场景中的效率和价值。同时，该框架深化了鲲鹏处理器的特性支持，并与openEuler生态深度融合，助力拓展了鲲鹏和openEuler在大模型领域的生态应用广度。

## 环境准备

### 硬件要求

| 类型           |     硬件要求                  |
|----------------| -----------------------------|
| 服务器         | 1台                           |
| CPU           | 鲲鹏>= 64 cores   |
| 内存         | >= 256 GB                 |
| 内存带宽        | >= 100 GB/s               |

### 权重模型

支持huggingface上的Baichuan2-13B和Llama3-8B等开源权重模型

```shell
mkdir -r /home/app
cd /home/app
# 以Baichuan2-13B-Chat-GGUF为例
wget https://hf-mirror.com/second-state/Baichuan2-13B-Chat-GGUF/resolve/main/Baichuan2-13B-Chat-Q4_0.gguf
# Llama3
wget https://hf-mirror.com/shenzhi-wang/Llama3-8B-Chinese-Chat-GGUF-4bit/resolve/main/Llama3-8B-Chinese-Chat-q4_0-v2_1.gguf
```

### docker镜像拉取

```shell
# oe_openai_server:0.0.1镜像
docker pull hub.oepkgs.net/neocopilot/oe_openai_server@sha256:2c87870fc34754391b1160bc0478f2691d0d47e47bb5a5bc18d8ec352d73fcb3
```



## 部署openai服务接口

### 接口部署

```shell
# 查看鲲鹏920系列服务器逻辑核分布情况，下面以鲲鹏920为例
lscpu
```
<img src="./pictures/CPU推理部署/CPU逻辑核心.png" alt="CPU逻辑核心分布图" style="zoom: 200%;" />

```shell
# 以鲲鹏920为例进行绑核，逻辑核总数设置4的倍数，绑核按numa节点平均分配
docker run -it \
    -v /home/app/Baichuan2-13B-Chat-Q4_0.gguf:/app/Baichuan2-13B-Chat-Q4_0.gguf \
    -p 7860:7860 \
    -e OMP_NUM_THREADS=88 \
    -e GOMP_CPU_AFFINITY=0-21,24-45,48-69,72-93 \
    hub.oepkgs.net/neocopilot/oe_openai_server:0.0.1 \
    ./server /app/Baichuan2-13B-Chat-Q4_0.gguf -t 0.0 -n 4096
```

### 接口功能测试

按照openai官方文档构建的python脚本，用于验证功能，验证无误后可接入EulerCopilot。

```python
# request.py
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:7860/v1")

completion = client.chat.completions.create(
  model="Baichuan2-13B-Chat-Q4_0",
  messages=[
    {"role": "system", "content": "你是智能问答机器人。"},
    {"role": "user", "content": "请你告诉我openEuler操作系统的发布规律。"}
  ],
  stream=True
)

for chunk in completion:
  print(chunk.choices[0].delta)

```

