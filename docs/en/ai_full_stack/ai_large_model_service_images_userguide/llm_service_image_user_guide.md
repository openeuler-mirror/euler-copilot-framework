# Containerized Packaging for AI Large Models Supporting Baichuan, ChatGLM, Spark

Pre-configured with relevant dependencies, available in both CPU and GPU versions to lower the barrier to use and enable out-of-the-box deployment.

## Pull Image (CPU Version)

```bash
docker pull openeuler/llm-server:1.0.0-oe2203sp3
```

## Pull Image (GPU Version)

```bash
docker pull icewangds/llm-server:1.0.0
```

## Download Model and Convert to GGUF Format

```bash
# Install huggingface
pip install huggingface-hub

# Download the model you want to deploy
export HF_ENDPOINT=https://hf-mirror.com
huggingface-cli download --resume-download baichuan-inc/Baichuan2-13B-Chat --local-dir /root/models/Baichuan2-13B-Chat --local-dir-use-symlinks False

# GGUF format conversion
cd /root/models/
git clone https://github.com/ggerganov/llama.cpp.git
python llama.cpp/convert-hf-to-gguf.py ./Baichuan2-13B-Chat
# Generated GGUF format model path: /root/models/Baichuan2-13B-Chat/ggml-model-f16.gguf
```

## Startup Methods

Requires Docker v25.0.0 or higher.

If using GPU images, nvidia-container-toolkit must be installed on the OS. Installation instructions can be found at <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html>.

docker-compose.yaml:

```yaml
version: '3'
services:
  model:
    image: <image>:<tag>   # Image name and tag
    restart: on-failure:5
    ports:
      - 8001:8000    # Listening port, modify "8001" to change the port
    volumes:
      - /root/models:/models  # Large model mount directory
    environment:
      - MODEL=/models/Baichuan2-13B-Chat/ggml-model-f16.gguf  # Model file path inside container
      - MODEL_NAME=baichuan13b  # Custom model name
      - KEY=sk-12345678  # Custom API Key
      - CONTEXT=8192  # Context size
      - THREADS=8    # CPU thread count, only needed for CPU deployment
    deploy: # Specify GPU resources, only needed for GPU deployment
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
CPU deployment: docker run -d --restart on-failure:5 -p 8001:8000 -v /root/models:/models -e MODEL=/models/Baichuan2-13B-Chat/ggml-model-f16.gguf -e MODEL_NAME=baichuan13b -e KEY=sk-12345678 openeuler/llm-server:1.0.0-oe2203sp3

GPU deployment: docker run -d --gpus all --restart on-failure:5 -p 8001:8000 -v /root/models:/models -e MODEL=/models/Baichuan2-13B-Chat/ggml-model-f16.gguf -e MODEL_NAME=baichuan13b -e KEY=sk-12345678 icewangds/llm-server:1.0.0
```

## Test Large Model API Call - Successful response indicates successful deployment

```bash
curl -X POST http://127.0.0.1:8001/v1/chat/completions \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer sk-12345678" \
     -d '{
           "model": "baichuan13b",
           "messages": [
             {"role": "system", "content": "You are a community assistant, please answer the following question."},
             {"role": "user", "content": "Who are you?"}
           ],
           "stream": false,
           "max_tokens": 1024
         }'
```
