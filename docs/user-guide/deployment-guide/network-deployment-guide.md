# Network Environment Deployment Guide

## Introduction

openEuler Copilot System is an intelligent Q&A tool. Using openEuler Copilot System can enhance the convenience of acquiring operating system knowledge and empower developers and operation personnel in the OS domain. As a tool for obtaining operating system knowledge, it enables productivity tools for operating systems (such as A-Ops / A-Tune / x2openEuler / EulerMaker / EulerDevOps / StratoVirt / iSulad), disrupts traditional command delivery methods, and evolves from traditional command delivery to natural semantics. Combined with the intelligent task planning capabilities, it lowers the threshold for developing and using operating system features.

### Main Component Overview

| Component                      | Port            | Description                  |
| ----------------------------- | --------------- | -------------------- |
| euler-copilot-framework       | 8002 (Internal Port) | Intelligent Agent Framework Service         |
| euler-copilot-web             | 8080            | Intelligent Agent Frontend Interface        |
| euler-copilot-rag             | 9988 (Internal Port) | Retrieval Augmented Service           |
| mysql                         | 3306 (Internal Port) | MySQL Database           |
| redis                         | 6379 (Internal Port) | Redis Database           |
| postgres                      | 5432 (Internal Port) | Vector Database             |
| secret_inject                 | None              | Configuration File Secure Copy Tool   |

## Environment Requirements

### Software Requirements

| Type        | Version Requirement                         | Description                                |
|------------| -------------------------------------|--------------------------------------|
| Operating System    | openEuler 22.03 LTS or above         | None                                   |
| K3s        | >= v1.30.2, with Traefik Ingress Tool   | K3s provides a lightweight Kubernetes cluster, easy to deploy and manage |
| Helm       | >= v3.15.3                           | Helm is a Kubernetes package management tool, aiming to quickly install, upgrade, and uninstall openEuler Copilot System services |
| python     | >=3.9.9                              | Python 3.9.9 or higher versions provide the runtime environment for model download and installation |

### Hardware Requirements

| Type           | Hardware Requirement                  |
|----------------| -----------------------------|
| Server         | 1 unit                           |
| CPU           | Kunpeng or x86_64, >= 32 cores     |
| RAM           | >= 64GB                      |
| Storage          | >= 500 GB                    |
| GPU           | Tesla V100 16GB, 4 units         |
| NPU           | NPU card or server supporting large model inference  |              

Note:

1. If there are no GPU or NPU resources, it is recommended to implement functionality by calling OpenAI interfaces. (Example interface: <https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions> Reference link: [API-KEY Acquisition and Configuration](https://help.aliyun.com/zh/dashscope/developer-reference/acquisition-and-configuration-of-api-key?spm=a2c4g.11186623.0.0.30e7694eaaxxGa))
2. Calling third-party OpenAI interfaces does not require installing high-version Python (>=3.9.9)
3. NVIDIA GPU support for Docker requires a newer version of Docker (>= v25.4.0)
4. If using a k8s cluster environment, there is no need to separately install k3s, requiring version >= 1.28

### Deployment Diagram

[Deployment Diagram](./pictures/Deployment_View.png)

## Obtaining openEuler Copilot System

- Download the latest deployment repository from the official Git repository of openEuler Copilot System [euler-copilot-framework](https://gitee.com/openeuler/euler-copilot-framework).
- If you are using Kubernetes, there is no need to install the k3s tool.

```bash
# Example download directory is home
cd /home
```

```bash
git clone https://gitee.com/openeuler/euler-copilot-framework.git
```

## Environment Preparation

The device must be connected to the internet and meet the minimum software and hardware requirements for openEuler Copilot System. After confirming that the server, hardware, drivers, etc., are ready, proceed with the environment preparation. To ensure successful initialization, follow the instructions, enter our script deployment directory, and execute the provided operation steps and script paths sequentially.

```bash
# Enter the deployment script directory
cd /home/euler-copilot-framework/deploy/scripts && tree
```

```bash
.
├── check_env.sh
├── download_file.sh
├── get_log.sh
├── install_tools.sh
└── prepare_docker.sh
```

| Sequence Number    | Step Content     | Related Command        | Description    |
|-------------- |----------|---------------------------------------------|------------------------------------------ |
|1| Environment Check        | `bash check_env.sh`      | Mainly checks the server's hostname, DNS, firewall settings, remaining disk space size, network, and SELinux settings  |
|2| File Download        | `bash download_file.sh`  | Downloads models bge-reranker-large, bge-mixed-mode |
|3| Install Deployment Tools    | `bash install_tools.sh v1.30.2+k3s1 v3.15.3 cn`  | Installs helm, k3s tools. Note: "cn" refers to using a mirror site, which can be omitted  |
|4| Domain Name Configuration       | Requires preparing 4 domain names `minio\authhub\eulercopilot\witchaind`  | Apply for domain names in advance or configure them in 'C:\Windows\System32\drivers\etc\hosts'. They must share the same root domain, e.g., `minio.test.com`, `authhub.test.com`, `eulercopilot.test.com`, `witchaind.test.com`  |
|5| Large Model Preparation      | Provide third-party OpenAI interface or locally deploy large models based on hardware   | Refer to the appendix section for local deployment of large models  |



## Installation

Your environment is now ready, and you can proceed with the installation process of openEuler Copilot System.

- Example download directory is home. Enter the Helm configuration file directory of the openEuler Copilot System repository.

  ```bash
  cd /home/euler-copilot-framework && ll
  ```

  ```bash
  total 28
  drwxr-xr-x  3 root root 4096 Aug 28 17:45 docs/
  drwxr-xr-x  5 root root 4096 Aug 28 17:45 deploy/
  ```

- View the deploy directory

  ```bash
  tree deploy
  ```

  ```bash
  deploy/chart
  ├── databases
  │   ├── Chart.yaml
  │   ├── configs
  │   ├── templates
  │   └── values.yaml
  ├── authhub
  │   ├── Chart.yaml
  │   ├── configs
  │   ├── templates
  │   └── values.yaml
  └── euler_copilot
      ├── Chart.yaml
      ├── configs
      ├── templates
      │   ├── NOTES.txt
      │   ├── rag
      │   └── web
      └── values.yaml
  ```
- Create Namespace

  ```bash
  kubectl create namespace euler-copilot
  ```

  Set Environment Variables

  ```bash
  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
  ```

### 1. Install Databases

- Edit values.yaml

  ```bash
  cd deploy/chart/databases
  ```

  ```bash
  vim values.yaml
  ```
  **Filling Instructions:**
  1. **Password Setting**: All passwords must be a combination of numbers and letters, and ensure all entries are filled accurately;
  2. **Domain Setting**: Based on previous domain configurations, correctly fill in the MinIO domain;
  3. **Image Tag Adjustment**: Adjust image tags (tag) according to the system architecture.

- Install Databases

  ```bash
  helm install -n euler-copilot databases .
  ```

- Check Pod Status

  ```bash
  kubectl -n euler-copilot get pods
  ```

  ```bash
  pgsql-deploy-databases-86b4dc4899-ppltc           1/1     Running   0          17d
  redis-deploy-databases-f8866b56-kj9jz             1/1     Running   0          17d
  minio-deploy-databases-6b8dfcdc5d-7d4td           1/1     Running   0          17d
  mongo-deploy-databases-85c75cbb-v88r6             1/1     Running   0          17d
  ```

- Troubleshooting

  - View Pod Logs
  
  ```bash
  kubectl -n euler-copilot logs minio-deploy-databases-6b8dfcdc5d-7d4td
  ```
  - Enter Pod

  ```bash
  kubectl -n euler-copilot exec pgsql-deploy-databases-86b4dc4899-ppltc -- bash
  ```
  ```bash
  # Connect to the database
  psql -U postgres -d postgres
  ```
  - Clear PVC

  ```bash
  kubectl -n euler-copilot get pvc
  ```

  ```bash
  kubectl -n euler-copilot delete pvc minio-pvc-databases
  ```
  - Update Configuration
  ```bash
  helm upgrade -n euler-copilot databases .
  ```

### 2. Install Authentication Platform Authhub

- Edit values.yaml

  ```bash
  cd ../authhub
  ```
  ```bash
  vim values.yaml
  ```
  **Filling Instructions:**
  1. **Password Setting**: All passwords must be a combination of numbers and letters, and ensure all entries are filled accurately;
  2. **Domain Setting**: Based on previous domain configurations, correctly fill in the authhub-web domain;
  3. **Image Tag Adjustment**: Adjust image tags (tag) according to the system architecture.

- Install AuthHub

  ```bash
  helm install -n euler-copilot authhub .
  ```

- Check Pod Status

  ```bash
  kubectl -n euler-copilot get pods
  ```

  ```bash
  NAME                                             READY   STATUS    RESTARTS   AGE
  authhub-backend-deploy-authhub-64896f5cdc-m497f   2/2     Running   0          16d
  authhub-web-deploy-authhub-7c48695966-h8d2p       1/1     Running   0          17d
  pgsql-deploy-databases-86b4dc4899-ppltc           1/1     Running   0          17d
  redis-deploy-databases-f8866b56-kj9jz             1/1     Running   0          17d
  minio-deploy-databases-6b8dfcdc5d-7d4td           1/1     Running   0          17d
  mongo-deploy-databases-85c75cbb-v88r6             1/1     Running   0          17d
  ```

- Login to AuthHub
  
  The AuthHub domain is `<authhub.test.com>` as an example. Input `https://authhub.test.com` in the browser, and the login interface is shown below:

  [Deployment Diagram](./pictures/authhub_login_interface.png)

  **AuthHub default login account is `administrator`, password is `changeme`.**

- Create Application eulercopilot

  [Deployment Diagram](./pictures/create_application_interface.png)
 
  Click **Create Application**, and fill in the following information:
  - **Application Name**: eulercopilot
  - **Application Homepage URL**: https://eulercopilot.test.com
  - **Application Callback Address (After Login)**: https://eulercopilot.test.com/api/auth/login
  - Click **Create** to complete the application creation process. The system will automatically generate a **Client ID** and **Client Secret**. Please save this pair of credentials, as they will be needed later in the `deploy/chart/euler_copilot/values.yaml` configuration file.
  
  [Deployment Diagram](./pictures/create_application_success_interface.png)

### 3. Install openEuler Copilot System

- Edit values.yaml

  ```bash
  cd ../euler_copilot
  ```
  ```bash
  vim values.yaml
  ```
  **Filling Instructions:**

  1. **Password Setting**: All passwords must be a combination of numbers and letters, and ensure all entries are filled accurately.
  2. **Domain Configuration**: Based on previous domain settings, correctly fill in the corresponding domains for eulercopilot and witchind.
  3. **Image Tag Adjustment**: Adjust container image tags (tag) according to system architecture requirements.
  4. **Volume Mount Directory**: Create and specify the correct volume mount path.
  5. **OIDC Settings**: Complete the correct OIDC configuration in the framework chapter.
  6. **Plugin Deployment (Optional)**: If choosing to deploy plugins, configure the model for Function Call. Note that deploying sglang requires a GPU-supported environment; refer to the appendix for details.

- Install openEuler Copilot System

  ```bash
  helm install -n euler-copilot service .
  ```

- Check Pod Status

  ```bash
  kubectl -n euler-copilot get pods
  ```

  Image pulling may take about one minute, so please be patient. After successful deployment, all Pod statuses should display as Running.

  ```bash
  NAME                                              READY   STATUS    RESTARTS   AGE
  authhub-backend-deploy-authhub-64896f5cdc-m497f   2/2     Running   0          10m
  authhub-web-deploy-authhub-7c48695966-h8d2p       1/1     Running   0          10m
  pgsql-deploy-databases-86b4dc4899-ppltc           1/1     Running   0          10m
  redis-deploy-databases-f8866b56-kj9jz             1/1     Running   0          10m
  mysql-deploy-databases-57f5f94ccf-sbhzp           2/2     Running   0          10m
  framework-deploy-service-bb5b58678-jxzqr          2/2     Running   0          8m
  rag-deploy-service-5b7887644c-sm58z               2/2     Running   0          10m
  web-deploy-service-74fbf7999f-r46rg               1/1     Running   0          10m
  ```

  **Troubleshooting:**

  When the Pod status shows as failed, it is recommended to follow these steps for troubleshooting:

  1. **Get Cluster Event Information**

     To better locate the reason for Pod failure, first check the events in the Kubernetes cluster. This can provide context information about Pod status changes.

     ```bash
     kubectl get events -n euler-copilot
     ```

  2. **Verify Image Pull Status**

     Confirm whether the container image was successfully pulled. If the image fails to load properly, it may be due to network issues or incorrect image repository configuration.

     ```bash
     k3s crictl images
     ```

  3. **Review Pod Logs**

     Check the logs of the relevant Pod to find possible error messages or abnormal behavior. This is particularly useful for diagnosing application-level issues.

     ```bash
     kubectl logs rag-deploy-service-5b7887644c-sm58z -n euler-copilot
     ```

  4. **Evaluate Resource Availability**

     Ensure the Kubernetes cluster has sufficient resources (such as CPU, memory, and storage) to support Pod operation. Insufficient resources may cause image pull failures or other performance issues.

     ```bash
     kubectl top nodes
     ```

  5. **Confirm k3s Version Compatibility**

     If encountering issues where image pulling fails and the image size is 0, check if your k3s version meets the minimum requirement (v1.30.2 or higher). Lower versions may have compatibility issues.

     ```bash
     k3s -v
     ```

  6. **Check OIDC Settings**

     Review the OIDC configuration in the `values.yaml` file for the framework, ensuring that authentication and authorization services are correctly set up, which is crucial for integrating external authentication services.

     ```bash
     cat /home/euler-copilot-framework/deploy/chart/euler_copilot/values.yaml | grep oidc
     ```
## Verification of Installation

Congratulations, **openEuler Copilot System** has been successfully deployed! To start your experience, enter `https://your-EulerCopilot-domain` in your browser to access the web interface of openEuler Copilot System:

Upon first access, you need to click the **Register Now** button on the page to create a new account and complete the login process.

[Web Login Interface](./pictures/WEB登录界面.png)  
[Web Interface](./pictures/WEB界面.png)

## Installing Plugins

For more details, refer to the document [Plugin Deployment Guide](./插件部署指南).

## Building Domain-Specific Intelligent Q&A

For more details, refer to the document [Local Asset Library Construction Guide](./本地资产库构建指南.md).

## Appendix

### Preparing Large Models

#### GPU Environment

Follow the steps below for deployment:

1. Download the model file:

   ```bash
   huggingface-cli download --resume-download Qwen/Qwen1.5-14B-Chat --local-dir Qwen1.5-14B-Chat
   ```

2. Create a terminal session named `control`:

   ```bash
   screen -S control
   ```

   ```bash
   python3 -m fastchat.serve.controller
   ```

   - Press `Ctrl+A+D` to move it to the background.

3. Create a new terminal session named `api`:

   ```bash
   screen -S api
   ```

   ```bash
   python3 -m fastchat.serve.openai_api_server --host 0.0.0.0 --port 30000 --api-keys sk-123456
   ```

   - Press `Ctrl+A+D` to move it to the background.
   - If the current Python version is 3.12 or 3.9, you can create a Python 3.10 virtual environment using conda:

   ```bash
   mkdir -p /root/py310
   ```

   ```bash
   conda create --prefix=/root/py310 python==3.10.14
   ```

   ```bash
   conda activate /root/py310
   ```

4. Create a new terminal session named `worker`:

   ```bash
   screen -S worker
   ```

   ```bash
   screen -r worker
   ```

   Install `fastchat` and `vllm`:

   ```bash
   pip install fschat vllm
   ```

   Install dependencies:

   ```bash
   pip install fschat[model_worker]
   ```

   ```bash
   python3 -m fastchat.serve.vllm_worker --model-path /root/models/Qwen1.5-14B-Chat/ --model-name qwen1.5 --num-gpus 8 --gpu-memory-utilization=0.7 --dtype=half
   ```

   - Press `Ctrl+A+D` to move it to the background.

5. Configure the file as follows and update the service:

   ```bash
   vim deploy/chart/euler_copilot/values.yaml
   ```

   Modify the following section:

   ```yaml
   llm:
     # Open-source large model, OpenAI-compatible API
     openai:
       url: "http://$(IP):30000"
       key: "sk-123456"
       model: qwen1.5
       max_tokens: 8192
   ```

#### NPU Environment

Refer to the link for NPU environment deployment: [MindIE Installation Guide](https://www.hiascend.com/document/detail/zh/mindie/10RC2/whatismindie/mindie_what_0001.html).

### FAQ

#### 1. Resolving Hugging Face Connection Errors

If you encounter the following connection error:

```text
urllib3.exceptions.NewConnectionError: <urllib3.connection.HTTPSConnection object>: Failed to establish a new connection: [Errno 101] Network is unreachable
```

Try the following solutions:

- Update the `huggingface_hub` package to the latest version:

  ```bash
  pip3 install -U huggingface_hub
  ```

- If network issues persist, try using a mirror site as the endpoint:

  ```bash
  export HF_ENDPOINT=https://hf-mirror.com
  ```

#### 2. Calling the Q&A API in the RAG Container

After entering the corresponding RAG Pod, you can send a POST request using the `curl` command to get the Q&A result. Ensure that the specific question text is provided in the request body.

```bash
curl -k -X POST "http://localhost:8005/kb/get_answer" \
     -H "Content-Type: application/json" \
     -d '{
           "question": "Your question",
           "kb_sn": "default_test",
           "fetch_source": true
         }'
```

#### 3. Resolving `helm upgrade` Errors

When the Kubernetes cluster is unreachable, you may encounter an error similar to:

```text
Error: UPGRADE FAILED: Kubernetes cluster unreachable
```

Ensure that the KUBECONFIG environment variable is set correctly to point to a valid configuration file:

```bash
echo "export KUBECONFIG=/etc/rancher/k3s/k3s.yaml" >> /root/.bashrc
source /root/.bashrc
```

#### 4. Failure to View Pod Logs

If you encounter permission denied errors when viewing Pod logs, check whether the proxy settings are configured correctly and add your local IP address to the `no_proxy` environment variable:

```bash
cat /etc/systemd/system/k3s.service.env
```

Edit the file to ensure it includes:

```bash
no_proxy=XXX.XXX.XXX.XXX
```

#### 5. Streaming Reply Issues with Large Models in GPU Environments

For cases where certain services cannot stream replies when calling large models via curl, try setting the `"stream"` parameter to `false` in the request. Additionally, ensure that a compatible version of the Pydantic library is installed:

```bash
pip install pydantic==1.10.13
```

#### 6. sglang Model Deployment Guide

Follow these steps to deploy a model based on sglang:

```bash
# 1. Activate the Conda environment named `myenv`, which is based on Python 3.10:
conda activate myenv

# 2. Install sglang and all its dependencies, specifying version 0.3.0:
pip install "sglang[all]==0.3.0"

# 3. Install flashinfer from the specified index, ensuring compatibility with your CUDA and PyTorch versions:
pip install flashinfer -i https://flashinfer.ai/whl/cu121/torch2.4/

# 4. Start the server using sglang with the following configuration:
python -m sglang.launch_server \
    --served-model-name Qwen2.5-32B \
    --model-path Qwen2.5-32B-Instruct-AWQ \
    --host 0.0.0.0 \
    --port 8001 \
    --api-key "sk-12345" \
    --mem-fraction-static 0.5 \
    --tp 8
```

- Verify installation:

  ```bash
  pip show sglang
  pip show flashinfer
  ```

**Notes:**
- API Key: Ensure the API key in the `--api-key` parameter is correct.
- Model Path: Ensure the path in the `--model-path` parameter is correct and the model files exist at that location.
- CUDA Version: Ensure CUDA 12.1 and PyTorch 2.4 are installed on your system, as `flashinfer` depends on these specific versions.
- Thread Pool Size: Adjust the thread pool size based on your GPU resources and expected load. For example, if you have 8 GPUs, use `--tp 8` to fully utilize them.

#### 7. Obtaining Embeddings

Send a POST request using curl to obtain embedding results:

```bash
curl -k -X POST http://$IP:8001/embedding \
     -H "Content-Type: application/json" \
     -d '{"texts": ["sample text 1", "sample text 2"]}'
```

Here, `$IP` is the internal network address of vectorize.

#### 8. Generating Certificates

To generate self-signed certificates, first download the [mkcert](https://github.com/FiloSottile/mkcert/releases) tool, then run the following commands:

```bash
mkcert -install
mkcert example.com
```

Finally, copy the generated certificate and private key into `values.yaml` and apply it to the Kubernetes Secret:

```bash
vim /home/euler-copilot-framework_openeuler/deploy/chart_ssl/traefik-secret.yaml
```

```bash
kubectl apply -f traefik-secret.yaml
```

#### 9. Pod Status Changes from Running to Pending or Completed

Pod status changes may be due to insufficient storage space on the host machine. Use `df -h` to check disk usage and ensure at least 30% free space is available. This helps maintain stable Pod operation.