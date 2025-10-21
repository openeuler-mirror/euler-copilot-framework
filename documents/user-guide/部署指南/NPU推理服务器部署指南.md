# NPU推理服务器部署指南
本指南是基于Atlas 800I A2推理服务器，使用昇腾开放的[Docker镜像仓库](https://www.hiascend.com/developer/ascendhub)，提供的昇腾软件Docker镜像来部署大模型和Embeddings服务的案例。

## 系统环境
- 操作系统：openEuler 22.03 LTS
- 硬件：Atlas 800I A2推理服务器
- 组件：Ascend NPU

## 驱动安装
- 安装依赖（使用openEuler官方源）
```bash
sudo dnf install -y make dkms gcc kernel-headers-$(uname -r) kernel-devel-$(uname -r)
```
- 下载驱动
```bash
# 已下载的驱动包为：
# Ascend-hdk-910b-npu-driver_24.1.rc3_linux-aarch64.run
# Ascend-hdk-910b-npu-firmware_7.5.0.1.129.run

# 设置权限并校验
chmod +x Ascend-hdk-*.run
```
- 安装驱动和固件
```bash
./Ascend-hdk-910b-npu-driver_24.1.rc3_linux-aarch64.run --check
```
```bash
./Ascend-hdk-910b-npu-firmware_7.5.0.1.129.run --check
```
```bash
# 安装驱动（全量安装）
sudo ./Ascend-hdk-910b-npu-driver_24.1.rc3_linux-aarch64.run --full --install-for-all
```
```bash
# 安装固件
sudo ./Ascend-hdk-910b-npu-firmware_7.5.0.1.129.run --full
```
- 重启并验证安装

```bash
reboot
```
```bash
npu-smi info -t board -i 0  # 查看0号卡信息
```
> **注意事项**：
> 1. 确保安装前已更新系统：`sudo dnf update -y`
> 2. 若内核升级过，需要重启进入新内核后再安装
> 3. 出现`npu-smi`命令找不到时，检查`/usr/local/Ascend/npu-smi`是否在PATH中

## 容器环境准备

- 安装Docker运行时


参考docker 运行时 安装步骤：
https://www.hiascend.com/document/detail/zh/mindx-dl/600/clusterscheduling/clusterschedulingig/clusterschedulingig/dlug_installation_017.html 

```bash
wget https://gitee.com/ascend/mind-cluster/releases/download/v6.0.0.SPC1/Ascend-docker-runtime_6.0.0.SPC1_linux-aarch64.run
```
```bash
./Ascend-docker-runtime_6.0.0.SPC1_linux-aarch64.run --install
```
- 申请下载权限并登录镜像仓库

```bash
docker login -u cn-south-1@HST3UGLECEMTZLJ17RUT swr.cn-south-1.myhuaweicloud.com
```

- 拉取镜像
```bash
docker pull swr.cn-south-1.myhuaweicloud.com/ascendhub/deepseek-r1-distill-llama-70b:0.1.1-arm64
```
```bash
docker pull swr.cn-south-1.myhuaweicloud.com/ascendhub/mis-tei:7.0.RC1-800I-A2-aarch64
```
## 模型部署
- 创建模型存储目录
```bash
mkdir -p /data/models/MindSDK/DeepSeek-R1-Distill-Llama-70B
```
```bash
chmod -R 777 /data/models  # 按需调整权限
```
- 安装ModelScope 
```bash
pip install modelscope
```
- 下载大模型权重
```bash
cd /data/models/MindSDK/DeepSeek-R1-Distill-Llama-70B
```
```bash
modelscope download --model deepseek-ai/DeepSeek-R1-Distill-Llama-70B --local_dir ./
```

## 服务启动（8张910B4为例）

- 大模型推理服务
```bash
docker run -itd --name=deepseek-70b \
  --privileged \
  --device=/dev/davinci0 --device=/dev/davinci1 \
  --device=/dev/davinci_manager --device=/dev/hisi_hdc \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
  -v /data/models/MindSDK:/model \
  -e ASCEND_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
  -p 8000:8000 \
  swr.cn-south-1.myhuaweicloud.com/ascendhub/deepseek-r1-distill-llama-70b:0.1.1-arm64
```

- Embedding服务
```bash 
# 8张卡
docker run -u root -itd --name=tei-embedding --net=host --privileged \
        -v /home/data/bge-m3:/home/HwHiAiUser/model \
        -e ASCEND_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \ 
        -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
        -v /usr/local/sbin:/usr/local/sbin:ro \
        swr.cn-south-1.myhuaweicloud.com/ascendhub/mis-tei:7.0.RC1-800I-A2-aarch64 BAAI/bge-m3 0.0.0.0 8090
```
```bash
# 单张卡
docker run -d --name=tei-embedding --net=host --privileged \
        -v /home/HwHiAiUser/model:/home/HwHiAiUser/model \
        --device=/dev/davinci5 \
        -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
        -v /usr/local/sbin:/usr/local/sbin:ro \
        swr.cn-south-1.myhuaweicloud.com/ascendhub/mis-tei:7.0.RC1-300l-Duo-aarch64 BAAl/bge-m3 0.0.0.0 8090
```

## 服务验证
- 检查容器状态
```bash
docker ps -a --filter "name=deepseek\|tei"
```
- 测试大模型接口
```bash
curl -X POST http://localhost:8000/openai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek-R1-Distill-Llama-70B",
    "messages": [{"role":"user","content":"你好"}],
    "temperature": 0.6
  }'
```

- 测试 Embeddings 接口
```bash
curl http://localhost:8090/embed \
  -X POST \
  -d '{"inputs":"测试文本"}' \
  -H "Content-Type: application/json"
```

## 修改配置文件
```bash
vim euler-copilot-framework_3/deploy/chart/euler_copilot/values.yaml
```
```
models:
  # 用于问答的大语言模型；需要OpenAI兼容的API
  answer:
    # [必需] API端点URL（请根据API提供商文档确认是否包含"v1"后缀）
    endpoint: https://$ip:$port/v1
    # [必需] API密钥；默认为空
    key: sk-123456
    # [必需] 模型名称
    name: qwen3-32b
    # [必需] 模型最大上下文长度；推荐>=8192
    ctxLength: 8192
    # 模型最大输出长度，推荐>=2048
    maxTokens: 8192
  # 用于函数调用的模型；推荐使用特定的推理框架
  functionCall:
    # 推理框架类型，默认为ollama
    # 可用框架类型：["vllm", "sglang", "ollama", "openai"]
    backend: openai
    # [必需] 模型端点；请根据API提供商文档确认是否包含"v1"后缀
    # 留空则使用与问答模型相同的配置
    endpoint: https://$ip:$port/v1
    # API密钥；留空则使用与问答模型相同的配置
    key: sk-123456
    # 模型名称；留空则使用与问答模型相同的配置
    name: qwen3-32b
    # 模型最大上下文长度；留空则使用与问答模型相同的配置
    ctxLength: 8192
    # 模型最大输出长度；留空则使用与问答模型相同的配置
    maxTokens: 8192
  # 用于数据嵌入的模型
  embedding:
    # 推理框架类型，默认为openai
    # [必需] Embedding API类型：["openai", "mindie"]
    type: openai
    # [必需] Embedding URL（需要包含"v1"后缀）
    endpoint: https://$ip:$port/v1
    # [必需] Embedding模型API密钥
    key: sk-123456
    # [必需] Embedding模型名称
    name: BAAI/bge-m3
```
## 更新服务
```bash
helm upgrade -n euler-copilot euler-copilot .
```
```bash
kubectl get pods -n euler-copilot
```
## 常见问题排查
1. **驱动加载失败**：
   - 执行`dmesg | grep npu`查看内核日志
   - 确认`npu-smi`输出正常设备信息

2. **容器启动失败**：
   - 检查设备挂载：`ls /dev/davinci*`
   - 查看容器日志：`docker logs -f deepseek-70b`

3. **模型加载缓慢**：
   - 确认权重文件完整：`sha256sum model.bin`
   - 检查存储性能：`hdparm -Tt /dev/sda`

4. **API响应超时**：
   - 调整docker CPU限制：`--cpuset-cpus=0-31`
   - 增加JVM内存：`-e JAVA_OPTS="-Xmx64G"`

> **性能优化提示**：
> - 使用`npu-smi`监控NPU利用率
> - 在docker run时添加`--cpuset-cpus`绑定CPU核心
> - 对大模型服务启用`--tensor-parallel 8`参数