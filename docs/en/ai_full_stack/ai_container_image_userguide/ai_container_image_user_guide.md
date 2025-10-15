# openEuler AI Container Image User Guide

## Introduction

The openEuler AI container images package SDKs for different hardware accelerators, along with AI frameworks and large-model applications. You only need to load the image and start a container in the target environment to develop or use AI applications, significantly reducing deployment and environment configuration time and improving efficiency.

## Obtain Images

Currently, openEuler provides container images for both Ascend and NVIDIA platforms. You can find them here:

- `docker.io/openeuler/cann`: SDK-type images that install the CANN software stack on top of the openEuler base image, for Ascend environments.
- `docker.io/openeuler/cuda`: SDK-type images that install the CUDA software stack on top of the openEuler base image, for NVIDIA environments.
- `docker.io/openeuler/pytorch`: AI framework images that install PyTorch on top of an SDK image; the applicable platform depends on the installed SDK.
- `docker.io/openeuler/tensorflow`: AI framework images that install TensorFlow on top of an SDK image; the applicable platform depends on the installed SDK.
- `docker.io/openeuler/llm`: Model application images that include specific large models and toolchains on top of an AI framework image; the applicable platform depends on the installed SDK.

For detailed classifications and tag conventions of AI container images, see [oEEP-0014](https://gitee.com/openeuler/TC/blob/master/oEEP/oEEP-0014%20openEuler%20AI容器镜像软件栈规范.md).

Because AI container images are typically large, it is recommended to pull the image to your development environment before starting a container:

```sh
docker pull image:tag
```

Here, `image` is the repository name, such as `openeuler/cann`, and `tag` is the target image tag. After the image is pulled, you can start the container. Note that to use the `docker pull` command, Docker must be installed as described below.

## Start a Container

1. Install `docker` in your environment. Refer to the official guide `https://docs.docker.com/engine/install/`, or install directly with the following commands:

    ```sh
    yum install -y docker
    ```

    or

    ```sh
    apt-get install -y docker
    ```

2. For NVIDIA environments, install `nvidia-container` components.

    (1) Configure yum or apt repositories
    - For yum-based systems, run:

    ```sh
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | \
    sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo
    ```

    - For apt-based systems, run:

    ```sh
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    ```

    ```sh
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    ```

    (2) Install `nvidia-container-toolkit` and `nvidia-container-runtime`:

    ```sh
    # yum installation
    yum install -y nvidia-container-toolkit nvidia-container-runtime
    ```

    ```sh
    # apt installation
    apt-get install -y nvidia-container-toolkit nvidia-container-runtime
    ```

    (3) Configure Docker

    ```sh
    nvidia-ctk runtime configure --runtime=docker
    systemctl restart docker
    ```

    Skip this step if you are not on an NVIDIA platform.

3. Ensure the appropriate `driver` and `firmware` are installed. You can obtain the correct versions from the official websites of [NVIDIA](https://www.nvidia.com/) or [Ascend](https://www.hiascend.com/). After installation, test with `npu-smi` for Ascend platforms or `nvidia-smi` for NVIDIA platforms. If hardware information is displayed correctly, the installation is successful.

4. After completing the above steps, use the `docker run` command to start a container.

```sh
# Start a container on an Ascend environment
docker run --rm --network host \
           --device /dev/davinci0:/dev/davinci0 \
           --device /dev/davinci_manager --device /dev/devmm_svm --device /dev/hisi_hdc \
           -v /usr/local/dcmi:/usr/local/dcmi -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
           -v /usr/local/Ascend/driver/lib64/:/usr/local/Ascend/driver/lib64/ \
           -ti image:tag
```

```sh
# Start a container on an NVIDIA environment
docker run --gpus all -d -ti image:tag
```
