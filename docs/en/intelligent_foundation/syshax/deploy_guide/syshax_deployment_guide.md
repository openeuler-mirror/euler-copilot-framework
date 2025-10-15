# sysHAX Deployment Guide

## Overview

sysHAX is positioned as K+X heterogeneous fusion inference acceleration, mainly consisting of two functional components:

- Inference dynamic scheduling
- CPU inference acceleration

**Inference dynamic scheduling**: For inference tasks, the prefill stage is a compute-intensive task, while the decode stage is memory-access intensive. Therefore, from the perspective of computing resources, the prefill stage is suitable for execution on hardware such as GPU/NPU, whereas the decode stage can be executed on hardware like CPU.

**CPU inference acceleration**: Accelerate CPU inference performance through NUMA affinity, parallel optimization, and operator optimization.

sysHAX includes two delivery components:

![syshax-deploy](pictures/syshax-deploy.png "syshax-deploy")

The delivery components include:

- sysHAX: responsible for request processing and scheduling of prefill and decode requests
- vllm: vllm is a large model inference service that includes both GPU/NPU and CPU versions during deployment, used for handling prefill and decode requests respectively. From the developer's usability perspective, vllm will be released in containerized form.

vllm is a **high-throughput, low-memory footprint** **large language model (LLM) inference and service engine** that supports **CPU computation acceleration**, providing an efficient operator dispatch mechanism, including:

- Schedule: Optimize task distribution to improve parallel computing efficiency
- Prepare Input: Efficient data preprocessing to accelerate input building
- Ray Framework: Utilize distributed computing to enhance inference throughput
- Sample (Model Post-processing): Optimize sampling strategies to improve generation quality
- Framework Post-processing: Integrate multiple optimization strategies to enhance overall inference performance

This engine combines **efficient computational scheduling and optimization strategies** to provide **faster, more stable, and scalable** solutions for LLM inference.

## Environment Preparation

| KEY        | VALUE                                   |
| ---------- | ---------------------------------------- |
| Server Model | Kunpeng 920 series CPU                  |
| GPU        | Nvidia A100                              |
| Operating System | openEuler 24.03 LTS SP1                 |
| Python     | 3.9 and above                            |
| Docker     | 25.0.3 and above                         |

- Docker 25.0.3 can be installed via `dnf install moby`.
- Note: sysHAX currently only supports NVIDIA GPU adaptation on AI acceleration cards, ASCEND NPU adaptation is in progress.

## Deployment Process

First, you need to check if the NVIDIA driver and CUDA driver are installed via `nvidia-smi` and `nvcc -V`. If not, you need to install the NVIDIA driver and CUDA driver first.

### Install NVIDIA Container Toolkit (Container Engine Plugin)

If NVIDIA Container Toolkit is already installed, you can skip this step. Otherwise, install it following the process below:

<https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html>

- Execute the `systemctl restart docker` command to restart Docker, so that the content added by the container engine plugin in the Docker configuration file takes effect.

### Container Scenario vllm Setup

The following process deploys vllm in a GPU container.

```shell
docker pull hub.oepkgs.net/neocopilot/syshax/syshax-vllm-gpu:0.2.1

docker run --name vllm_gpu \
    --ipc="shareable" \
    --shm-size=64g \
    --gpus=all \
    -p 8001:8001 \
    -v /home/models:/home/models \
    -w /home/ \
    -itd hub.oepkgs.net/neocopilot/syshax/syshax-vllm-gpu:0.2.1 bash
```

In the above script:

- `--ipc="shareable"`: Allows containers to share IPC namespaces for inter-process communication.
- `--shm-size=64g`: Sets container shared memory to 64G.
- `--gpus=all`: Allows containers to use all GPU devices on the host machine.
- `-p 8001:8001`: Port mapping, mapping port 8001 of the host machine to port 8001 of the container, which can be modified by developers.
- `-v /home/models:/home/models`: Directory mounting, mapping the host's `/home/models` to the container's `/home/models`, achieving model sharing. Developers can modify the mapping directory as needed.

```shell
vllm serve /home/models/DeepSeek-R1-Distill-Qwen-32B \
    --served-model-name=ds-32b \
    --host 0.0.0.0 \
    --port 8001 \
    --dtype=auto \
    --swap_space=16 \
    --block_size=16 \
    --preemption_mode=swap \
    --max_model_len=8192 \
    --tensor-parallel-size 2 \
    --gpu_memory_utilization=0.8 \
    --enable-auto-pd-offload
```

In the above script:

- `--tensor-parallel-size 2`: Enable tensor parallelism, splitting the model to run on 2 GPUs, requiring at least 2 GPUs, which can be modified by developers.
- `--gpu_memory_utilization=0.8`: Limit GPU memory utilization to 80% to prevent service crashes due to memory exhaustion, which can be modified by developers.
- `--enable-auto-pd-offload`: Enable PD separation when triggering swap out.

The following process deploys vllm in a CPU container.

```shell
docker pull hub.oepkgs.net/neocopilot/syshax/syshax-vllm-cpu:0.2.1

docker run --name vllm_cpu \
    --ipc container:vllm_gpu \
    --shm-size=64g \
    --privileged \
    -p 8002:8002 \
    -v /home/models:/home/models \
    -w /home/ \
    -itd hub.oepkgs.net/neocopilot/syshax/syshax-vllm-cpu:0.2.1 bash
```

In the above script:

- `--ipc container:vllm_gpu` shares the IPC (inter-process communication) namespace of the container named vllm_gpu. This allows this container to exchange data directly through shared memory, avoiding cross-container copying.

```shell
NRC=4 INFERENCE_OP_MODE=fused OMP_NUM_THREADS=160 CUSTOM_CPU_AFFINITY=0-159 SYSHAX_QUANTIZE=q4_0 \
vllm serve /home/models/DeepSeek-R1-Distill-Qwen-32B \
    --served-model-name=ds-32b \
    --host 0.0.0.0 \
    --port 8002 \
    --dtype=half \
    --block_size=16 \
    --preemption_mode=swap \
    --max_model_len=8192 \
    --enable-auto-pd-offload
```

In the above script:

- `INFERENCE_OP_MODE=fused`: Enable CPU inference acceleration
- `OMP_NUM_THREADS=160`: Specify the number of threads for CPU inference startup as 160. This environment variable only takes effect after setting INFERENCE_OP_MODE=fused.
- `CUSTOM_CPU_AFFINITY=0-159`: Specify the CPU binding scheme, which will be described in detail later.
- `SYSHAX_QUANTIZE=q4_0`: Specify the quantization scheme as q4_0. The current version supports 2 quantization schemes: `q8_0` and `q4_0`.
- `NRC=4`: GEMV operator block mode. This environment variable provides good acceleration effects on 920 series processors.

Note that the GPU container must be started before the CPU container can be started.

Use lscpu to check the current machine's hardware situation, focusing on:

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

This machine has a total of 160 physical cores, with SMT disabled, and has 4 NUMA nodes, each with 40 cores.

Set the CPU binding scheme using these two scripts: `OMP_NUM_THREADS=160 CUSTOM_CPU_AFFINITY=0-159`. In these two environment variables, the first specifies the number of threads for CPU inference startup, and the second specifies the IDs of the bound CPUs. To achieve NUMA affinity in CPU inference acceleration, CPU binding operations are required, following the rules below:

- The number of startup threads must match the number of bound CPUs;
- The number of CPUs used on each NUMA must be the same to maintain load balancing.

For example, in the above script, CPUs 0-159 are bound. Among them, 0-39 belongs to NUMA node 0, 40-79 belongs to NUMA node 1, 80-119 belongs to NUMA node 2, and 120-159 belongs to NUMA node 3. Each NUMA uses 40 CPUs, ensuring load balancing for each NUMA.

### sysHAX Installation

There are two ways to install sysHAX: you can install the rpm package via dnf. Note that this method requires upgrading openEuler to openEuler 24.03 LTS SP2 or higher version:

```shell
dnf install sysHAX
```

Or directly start using the source code:

```shell
git clone -b v0.2.0 https://gitee.com/openeuler/sysHAX.git
```

Before starting sysHAX, some basic configurations are required:

```shell
# When installing sysHAX via dnf install sysHAX
syshax init
syshax config services.gpu.port 8001
syshax config services.cpu.port 8002
syshax config services.conductor.port 8010
syshax config models.default ds-32b
```

```shell
# When using git clone -b v0.2.0 https://gitee.com/openeuler/sysHAX.git
python3 cli.py init
python3 cli.py config services.gpu.port 8001
python3 cli.py config services.cpu.port 8002
python3 cli.py config services.conductor.port 8010
python3 cli.py config models.default ds-32b
```

Additionally, you can use `syshax config --help` or `python3 cli.py config --help` to view all configuration commands.

After configuration, start the sysHAX service using the following command:

```shell
# When installing sysHAX via dnf install sysHAX
syshax run
```

```shell
# When using git clone -b v0.2.0 https://gitee.com/openeuler/sysHAX.git
python3 main.py
```

When starting the sysHAX service, connectivity testing will be performed. sysHAX complies with the openAPI standard. After the service starts, you can call the large model service via API. The following script can be used for testing:

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
