# sysHAX部署指南

## 概述

sysHAX功能定位为K+X异构融合推理加速，主要包含两部分功能：

- 推理动态调度
- CPU推理加速

**推理动态调度**：对于推理任务，prefill阶段属于计算密集型任务，decode阶段属于访存密集型任务。因此从计算资源的角度来说，prefill阶段适合在GPU/NPU等硬件上执行，而decode阶段可以放在CPU等硬件上执行。
**CPU推理加速**：在CPU上通过NUMA亲和、并行优化、算子优化等方式，来加速CPU推理性能。

sysHAX共包含两部分交付件：

![syshax-deploy](pictures/syshax-deploy.png)
交付件包括：

- sysHAX：负责请求的处理和prefill、decode请求的调度
- vllm：vllm是一款大模型推理服务，在部署时包含GPU/NPU和CPU两种，分别用于处理prefill和decode请求。从开发者使用易用性角度来说，vllm将使用容器化发布。

vllm是一款**高吞吐、低内存占用**的**大语言模型（LLM）推理与服务引擎**，支持**CPU 计算加速**，提供高效的算子下发机制，包括：

- Schedule（调度）：优化任务分发，提高并行计算效率
- Prepare Input（准备数据）：高效的数据预处理，加速输入构建
- Ray 框架：利用分布式计算提升推理吞吐
- Sample（模型后处理）：优化采样策略，提升生成质量
- 框架后处理：融合多种优化策略，提升整体推理性能

该引擎结合**高效计算调度与优化策略**，为 LLM 推理提供**更快、更稳定、更可扩展**的解决方案。

## 环境准备

| 服务器型号  |  鲲鹏920系列CPU                           |
| ---------- | ----------------------------------------- |
| GPU        |  Nvidia A100                              |
| 操作系统    | openEuler 22.03 LTS及以上                 |
| python     | 3.9及以上                                 |
| docker     | 25.0.3及以上                              |

- docker 25.0.3可通过 `dnf install moby` 进行安装。

## 部署流程

首先需要通过 `nvidia-smi` 和 `nvcc -V` 检查是否已经安装好了nvidia驱动和cuda驱动，如果没有的话需要首先安装nvidia驱动和cuda驱动。

### 安装NVIDIA Container Toolkit（容器引擎插件）

已经安装NVIDIA Container Toolkit可忽略该步骤。否则按照如下流程安装：

<https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html>

- 执行 `systemctl restart docker` 命令重启docker，使容器引擎插件在docker配置文件中添加的内容生效。

### 容器场景vllm搭建

如下流程为在GPU容器中部署vllm。

```shell
docker pull hub.oepkgs.net/neocopilot/syshax/syshax-vllm-gpu:0.2.0

docker run --name vllm_gpu \
    --ipc="shareable" \
    --shm-size=64g \
    --gpus=all \
    -p 8001:8001 \
    -v /home/models:/home/models \
    -w /home/ \
    -itd hub.oepkgs.net/neocopilot/syshax/syshax-vllm-gpu:0.2.0 bash
```

在上述脚本中：

- `--ipc="shareable"`：允许容器共享IPC命名空间，可进行进程间通信。
- `--shm-size=64g`：设置容器共享内存为64G。
- `--gpus=all`：允许容器使用宿主机所有GPU设备
- `-p 8001:8001`：端口映射，将宿主机的8001端口与容器的8001端口进行映射，开发者可自行修改。
- `-v /home/models:/home/models`：目录挂载，将宿主机的 `/home/models` 映射到容器内的 `/home/models` 内，实现模型共享。开发者可自行修改映射目录。

```shell
vllm serve /home/models/DeepSeek-R1-Distill-Qwen-32B \
    --served-model-name=ds-32b \
    --host 0.0.0.0 \
    --port 8001 \
    --dtype=half \
    --swap_space=16 \
    --block_size=16 \
    --preemption_mode=swap \
    --max_model_len=8192 \
    --tensor-parallel-size 2 \
    --gpu_memory_utilization=0.8
```

在上述脚本中：

- `--tensor-parallel-size 2`：启用张量并行，将模型拆分到2张GPU上运行，需至少2张GPU，开发者可自行修改。
- `--gpu_memory_utilization=0.8`：限制显存使用率为80%，避免因为显存耗尽而导致服务崩溃，开发者可自行修改。

如下流程为在CPU容器中部署vllm。

```shell
docker pull hub.oepkgs.net/neocopilot/syshax/syshax-vllm-cpu:0.2.0

docker run --name vllm_cpu \
    --ipc container:vllm_gpu \
    --shm-size=64g \
    --privileged \
    -p 8002:8002 \
    -v /home/models:/home/models \
    -w /home/ \
    -itd hub.oepkgs.net/neocopilot/syshax/syshax-vllm-cpu:0.2.0 bash
```

在上述脚本中：

- `--ipc container:vllm_gpu`共享名为vllm_gpu的容器的IPC（进程间通信）命名空间。允许此容器直接通过共享内存交换数据，避免跨容器复制。

```shell
INFERENCE_OP_MODE=fused OMP_NUM_THREADS=160 CUSTOM_CPU_AFFINITY=0-159 SYSHAX_QUANTIZE=q8_0 \
vllm serve /home/models/DeepSeek-R1-Distill-Qwen-32B \
    --served-model-name=ds-32b \
    --host 0.0.0.0 \
    --port 8002 \
    --dtype=half \
    --block_size=16 \
    --preemption_mode=swap \
    --max_model_len=8192
```

在上述脚本中：

- `INFERENCE_OP_MODE=fused`：启动CPU推理加速
- `OMP_NUM_THREADS=160`：指定CPU推理启动线程数为160，该环境变量需要在指定INFERENCE_OP_MODE=fused后才能生效
- `CUSTOM_CPU_AFFINITY=0-159`：指定CPU绑核方案，后续会详细介绍。
- `SYSHAX_QUANTIZE=q8_0`：指定量化方案为q8_0。当前版本支持2种量化方案：`q8_0`、`q4_0`。

需要注意的是，必须先启动GPU的容器，才能启动CPU的容器。

通过lscpu来检查当前机器的硬件情况，其中重点需要关注的是：

```shell
Architecture:             aarch64
  CPU op-mode(s):         64-bit
  Byte Order:             Little Endian
CPU(s):                   160
  On-line CPU(s) list:    0-159
Vendor ID:                HiSilicon
  BIOS Vendor ID:         HiSilicon
  Model name:             -
    Model:                0
    Thread(s) per core:   1
    Core(s) per socket:   80
    Socket(s):            2
NUMA:
  NUMA node(s):           4
  NUMA node0 CPU(s):      0-39
  NUMA node1 CPU(s):      40-79
  NUMA node2 CPU(s):      80-119
  NUMA node3 CPU(s):      120-159
```

该机器共有160个物理核心，没有开启SMT，共有4个NUMA，每个NUMA上有40个核心。

通过这两条脚本来设定绑核方案：`OMP_NUM_THREADS=160 CUSTOM_CPU_AFFINITY=0-159`。在这两条环境变量中，第一条为CPU推理启动线程数，第二条为绑定的CPU的ID。在 CPU推理加速中为实现NUMA亲和，需要进行绑核操作，要遵循如下规则：

- 启动线程数要与绑定的CPU个数相同；
- 每一个NUMA上使用的CPU个数需要相同，以保持负载均衡。

例如，在上述脚本中，绑定了0-159号CPU。其中，0-39属于0号NUMA节点，40-79属于1号NUMA节点，80-119属于2号NUMA节点，120-159属于3号NUMA节点。每个NUMA均使用了40个CPU，保证了每个NUMA的负载均衡。

### sysHAX安装

sysHAX安装：

```shell
dnf install sysHAX
```

在启动sysHAX之前需要进行一些基础配置：

```shell
syshax init
syshax config services.gpu.port 8001
syshax config services.cpu.port 8002
syshax config services.conductor.port 8010
syshax config models.default ds-32b
```

此外，也可以通过 `syshax config --help` 来查看全部配置命令。

配置完成后，通过如下命令启动sysHAX服务：

```shell
syshax run
```

启动sysHAX服务的时候，会进行服务连通性测试。sysHAX符合openAPI标准，待服务启动完成后，即可API来调用大模型服务。可通过如下脚本进行测试：

```shell
curl http://0.0.0.0:8010/v1/chat/completions -H "Content-Type: application/json" -d '{
    "model": "ds-32b",
    "messages": [
        {
            "role": "user",
            "content": "介绍一下openEuler。"
        }
    ],
    "stream": true,
    "max_tokens": 1024
}'
```
