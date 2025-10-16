# openEuler AI 容器镜像用户指南

## 简介

openEuler AI 容器镜像封装了不同硬件算力的 SDK 以及 AI 框架、大模型应用等软件，用户只需要在目标环境中加载镜像并启动容器，即可进行 AI 应用开发或使用，大大减少了应用部署和环境配置的时间，提升效率。

## 获取镜像

目前，openEuler 已发布支持 Ascend 和 NVIDIA 平台的容器镜像，获取路径如下：

- `docker.io/openeuler/cann` 存放 SDK 类镜像，在 openEuler 基础镜像之上安装 CANN 系列软件，适用于 Ascend 环境。
- `docker.io/openeuler/cuda` 存放 SDK 类镜像，在 openEuler 基础镜像之上安装 CUDA 系列软件，适用于 NVIDIA 环境。
- `docker.io/openeuler/pytorch` 存放 AI 框架类镜像，在 SDK 镜像基础之上安装 PyTorch，根据安装的 SDK 软件内容区分适用平台。
- `docker.io/openeuler/tensorflow` 存放 AI 框架类镜像，在 SDK 镜像基础之上安装 TensorFlow，根据安装的 SDK 软件内容区分适用平台。
- `docker.io/openeuler/llm` 存放模型应用类镜像，在 AI 框架镜像之上包含特定大模型及工具链，根据安装的 SDK 软件内容区分适用平台。

详细的 AI 容器镜像分类和镜像 tag 的规范说明见[oEEP-0014](https://gitee.com/openeuler/TC/blob/master/oEEP/oEEP-0014%20openEuler%20AI容器镜像软件栈规范.md)。

由于 AI 容器镜像的体积一般较大，推荐用户在启动容器前先通过如下命令将镜像拉取到开发环境中。

```sh
docker pull image:tag
```

其中，`image`为仓库名，如`openeuler/cann`，`tag`为目标镜像的 TAG，待镜像拉取完成后即可启动容器。注意，使用`docker pull`命令需按照下文方法安装`docker`软件。

## 启动容器

1. 在环境中安装`docker`，官方安装方法见 `https://docs.docker.com/engine/install/`，也可直接通过如下命令进行安装。

    ```sh
    yum install -y docker
    ```

    或

    ```sh
    apt-get install -y docker
    ```

2. NVIDIA环境安装`nvidia-container`

    1）配置yum或apt repo
    - 使用yum安装时，执行：

    ```sh
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | \
    sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo
    ```

    - 使用apt安装时，执行：

    ```sh
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    ```

    ```sh
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    ```

    2）安装`nvidia-container-toolkit`,`nvidia-container-runtime`，执行：

    ```sh
    # yum安装
    yum install -y nvidia-container-toolkit nvidia-container-runtime
    ```

    ```sh
    # apt安装
    apt-get install -y nvidia-container-toolkit nvidia-container-runtime
    ```

    3）配置docker

    ```sh
    nvidia-ctk runtime configure --runtime=docker
    systemctl restart docker
    ```

    非NVIDIA环境不执行此步骤。

3. 确保环境中安装`driver`及`firmware`，用户可从[NVIDIA](https://www.nvidia.com/)或[Ascend](https://www.hiascend.com/)官网获取正确版本进行安装。安装完成后 Ascend 平台使用`npu-smi`命令、NVIDIA 平台使用`nvidia-smi`进行测试，正确显示硬件信息则说明安装正常。

4. 完成上述操作后，即可使用`docker run`命令启动容器。

```sh
# Ascend环境启动容器
docker run --rm --network host \
           --device /dev/davinci0:/dev/davinci0 \
           --device /dev/davinci_manager --device /dev/devmm_svm --device /dev/hisi_hdc \
           -v /usr/local/dcmi:/usr/local/dcmi -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
           -v /usr/local/Ascend/driver/lib64/:/usr/local/Ascend/driver/lib64/ \
           -ti image:tag
```

```sh
# NVIDIA环境启动容器
docker run --gpus all -d -ti image:tag
```
