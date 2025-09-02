# Smart Tuning Deployment Guide

## Prerequisites

+ Install [EulerCopilot Command Line (Smart Shell) Client](../../../quick_start/smart_shell/user_guide/shell.md) in advance

+ The machine to be tuned must be openEuler 22.03 LTS-SP3

+ Install dependencies on the machine that needs to be tuned

```bash
yum install -y sysstat perf
```

+ The machine to be tuned must have SSH port 22 enabled

## Edit Configuration File

Modify the tune section in the values.yaml file, change the `enable` field to `True`, and configure the large language model settings,
Embedding model file address, as well as the machines that need tuning and their corresponding MySQL account names and passwords

```bash
vim /home/euler-copilot-framework/deploy/chart/agents/values.yaml
```

```yaml
tune:
    # [Required] Whether to enable Smart Tuning Agent
    enabled: true
    # Image settings
    image:
      # Image registry. Leave empty to use global settings.
      registry: ""
      # [Required] Image name
      name: euler-copilot-tune
      # [Required] Image tag
      tag: "0.9.1"
      # Pull policy. Leave empty to use global settings.
      imagePullPolicy: ""
    # [Required] Container root directory read-only
    readOnly: false
    # Performance limit settings
    resources: {}
    # Service settings
    service:
      # [Required] Service type, ClusterIP or NodePort
      type: ClusterIP
      nodePort: 
    # Large language model settings
    llm:
      # [Required] Model address (must include v1 suffix)
      url: 
      # [Required] Model name
      name: ""
      # [Required] Model API Key
      key: ""
      # [Required] Maximum tokens for the model
      max_tokens: 8096
    # [Required] Embedding model file address
    embedding: ""
    # Target optimization machine information
    machine:
      # [Required] IP address
      ip: ""
      # [Required] Root user password
      # Note: Root user must be enabled for SSH login with password
      password: ""
    # Target optimization application settings
    mysql:
      # [Required] Database username
      user: "root"
      # [Required] Database password
      password: ""
```

## Install Smart Tuning Plugin

```bash
helm install -n euler-copilot agents .
```

If you have installed before, update the plugin service with the following command

```bash
helm upgrade-n euler-copilot agents .
```

If the framework has not been restarted, you need to restart the framework configuration

```bash
kubectl delete pod framework-deploy-service-bb5b58678-jxzqr -n eulercopilot
```

## Testing

+ Check the tune pod status

  ```bash
  NAME                                             READY   STATUS    RESTARTS   AGE
  authhub-backend-deploy-authhub-64896f5cdc-m497f   2/2     Running   0          16d
  authhub-web-deploy-authhub-7c48695966-h8d2p       1/1     Running   0          17d
  pgsql-deploy-databases-86b4dc4899-ppltc           1/1     Running   0          17d
  redis-deploy-databases-f8866b56-kj9jz             1/1     Running   0          17d
  mysql-deploy-databases-57f5f94ccf-sbhzp           2/2     Running   0          17d
  framework-deploy-service-bb5b58678-jxzqr          2/2     Running   0          16d
  rag-deploy-service-5b7887644c-sm58z               2/2     Running   0          110m
  web-deploy-service-74fbf7999f-r46rg               1/1     Running   0          2d
  tune-deploy-agents-5d46bfdbd4-xph7b               1/1     Running   0          2d
  ```

+ Pod startup failure troubleshooting methods
  + Check the `servers.url` field in the openapi.yaml under the euler-copilot-tune directory to ensure the tuning service startup address is correctly set
  + Check if the `$plugin_dir` plugin folder path is correctly configured. This variable is located in the `framework` module in `deploy/chart/euler_copilot/values.yaml`. If the plugin directory doesn't exist, create it, and place the euler-copilot-tune folder from that directory into `$plugin_dir`.
  + Check if the sglang address and key are correctly filled. This variable is located in `vim /home/euler-copilot-framework/deploy/chart/euler_copilot/values.yaml`

    ```yaml
      # Model for Function Call
      scheduler:
        # Inference framework type
        backend: sglang
        # Model address
        url: ""
        # Model API Key
        key: ""
      # Database settings
    ```
