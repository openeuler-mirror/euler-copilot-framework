# 智能助手 CLI（Witty Assistant）安装指南

本手册适用于 Witty Assistant 2.0.0 版本。

## 环境要求

- **操作系统**：openEuler 24.03 LTS SP3 或更高版本
- **内存**：至少 8GB RAM
- **存储**：至少 20GB 可用磁盘空间
- **网络**：稳定的互联网连接（如需离线部署，请提前准备所需资源，详见 FAQ）
- **大模型服务**：
  - 线上：需具备支持工具调用的线上大模型 API 访问权限，例如百炼、DeepSeek Chat、智谱、MiniMax、硅基流动等
  - 本地：支持部署在本地的 LLM 服务，如 llama-server、ollama、vLLM、LM Studio 等，需使用支持工具调用的大模型，例如 Qwen3、DeepSeek 3.2、GLM-4.7、MiniMax M2.1、Kimi K2 等
- **系统权限**：需具备 sudo 权限，以便安装必要的软件包和依赖项

## 快速开始

### 安装 Witty Assistant

openEuler 24.03 LTS SP3 标准镜像已预装 Witty Assistant。开始使用前，请先运行以下命令更新系统软件包：

```bash
sudo dnf update -y
```

如需手动安装 Witty Assistant，请执行：

```bash
sudo dnf install -y witty-assistant
```

### 初始化 Witty Assistant

```bash
sudo witty init
```

![选择连接现有服务或部署新服务](./pictures/witty-deploy-01-welcome.png)

部署全新服务过程中涉及安装 RPM 包，请确保使用具有管理员权限的用户执行该命令。

**说明**：命令行客户端的界面样式会因终端适配情况而异，建议使用支持 256 色及以上的终端模拟器以获得最佳体验。本文档示例基于 Windows 11 内置终端通过 SSH 连接 openEuler。

### 选择部署新服务

在欢迎界面选择“部署新服务”，Witty Assistant 将执行环境检查。

![选择部署新服务](./pictures/witty-deploy-02-env-check.png)

选择“继续配置”，进入参数配置界面。

### 配置参数

在参数配置界面中，请根据实际情况设置以下参数：

![LLM 配置标签页](./pictures/witty-deploy-03-llm-tab.png)

依次配置大模型服务参数：

- **API 端点**：填写线上或本地大模型服务的 API 地址
- **API 密钥**：根据所选大模型服务要求，填写 API Key 或 Token
- **模型名称**：选择要使用的大模型

请确保所选大模型支持工具调用功能，否则智能体将无法正常工作。

![填写大模型信息](./pictures/witty-deploy-04-llm-fill-in.png)

**Embedding 模型配置：**

切换至“Embedding 配置”标签页，填写 Embedding 相关参数：

![Embedding 配置标签页](./pictures/witty-deploy-05-embd-tab.png)

![填写 Embedding 信息](./pictures/witty-deploy-06-embd-fill-in.png)

支持的 Embedding 端口格式包括 OpenAI 兼容格式和 TEI 格式，请根据实际情况填写。

### 启动部署

完成大模型配置后，点击下方“开始部署”按钮以启动部署程序。

![开始部署](./pictures/witty-deploy-07-start.png)

![部署进行中](./pictures/witty-deploy-08-ing.png)

部署过程可能需要较长时间，请耐心等待。部署完成后，系统将提示成功信息。

![部署完成](./pictures/witty-deploy-09-finish.png)

轻量部署模式完成后，将显示已初始化的智能体以及自动配置的默认智能体。

### 其他配置

部署完成后，您可进行以下配置：

- **设置默认智能体**（仅适用于 sysAgent 后端）：

  ```bash
  witty set-default agent
  ```

- **管理 LLM 配置**（需管理员权限，仅适用于 sysAgent 后端）：

  ```bash
  sudo witty llm
  ```

- **查看日志**：

  ```bash
  witty logs
  ```

- **设置日志级别**：

  ```bash
  witty set-default log-level INFO
  ```

## 附录

### 离线环境使用大模型服务

#### 内网大模型 API 服务

若内网环境中的大模型服务需通过 HTTPS 访问，请确保证书已在系统中正确配置，以避免部署过程中出现证书验证失败的问题。如无法配置有效证书，请在环境变量中添加以下内容以跳过证书验证：

```bash
export OI_SKIP_SSL_VERIFY=true
```

建议将上述命令添加至 `~/.bashrc` 或 `~/.bash_profile` 文件中，以确保每次登录时均设置该环境变量。

#### 本地部署大模型服务

若无可用的大模型服务，可在本地部署一个支持工具调用能力的大模型服务。sysAgent 支持标准的 OpenAI API（v1/chat/completions）。

若本地设备无 GPU，建议使用激活参数较少的 MoE 模型，例如 Qwen3-30B-A3B，以获得更佳的性能表现。本地部署大模型需要较大的计算资源，建议使用至少具备 32GB 内存和多核 CPU 的服务器或 PC 进行部署。

#### 为 sysAgent 配置代理

若内网环境需要通过代理服务器访问大模型服务，请在 `sysagent` 的服务文件（`/etc/systemd/system/sysagent.service`）中设置以下内容：

```bash
[Service]
Environment="HTTP_PROXY=http://<proxy-server>:<port>"
Environment="HTTPS_PROXY=http://<proxy-server>:<port>"
Environment="NO_PROXY=localhost,127.0.0.1"
```

请将 `<proxy-server>` 和 `<port>` 替换为实际的代理服务器地址和端口号。保存文件后，执行以下命令以重新加载服务配置并重启 `sysagent` 服务：

```bash
sudo systemctl daemon-reload
sudo systemctl restart sysagent
```

### FAQ

#### Q1：如何设置安装界面的语言？

**A1**：安装界面的默认语言会根据终端的语言环境变量自动选择。可通过设置 `LANG` 环境变量来指定语言，例如：

```bash
export LANG=zh_CN.UTF-8  # 设置为中文
export LANG=en_US.UTF-8  # 设置为英文
```

部署完成后，如需更改界面语言，可在命令行中使用以下命令：

```bash
witty set-default locale zh_CN  # 切换到中文
witty set-default locale en_US  # 切换到英文
```

#### Q2：部署过程中 pip 包下载缓慢怎么办？

**A2**：可使用国内 pip 镜像源，例如清华大学的镜像源。通过修改 pip 配置文件来使用清华镜像源：

```bash
mkdir -p ~/.pip
echo "[global]" > ~/.pip/pip.conf
echo "index-url = https://pypi.tuna.tsinghua.edu.cn/simple" >> ~/.pip/pip.conf
```

#### Q3：如无法访问外网，如何获取所需的依赖包？

**A3**：可在有外网的环境中下载所需的依赖包，然后传输至目标环境进行安装。具体步骤如下：

1. 在有外网的环境中，使用以下命令下载所需依赖包：

    ```bash
    pip download -d /path/to/download/dir <package-name>
    ```

    请将 `<package-name>` 替换为实际需要下载的包名，`/path/to/download/dir` 替换为实际的下载目录。

2. 将下载的依赖包拷贝到目标环境中。

3. 在目标环境中，使用以下命令安装依赖包：

    ```bash
    pip install --no-index --find-links=/path/to/download/dir <package-name>
    ```

    请将 `/path/to/download/dir` 替换为实际的下载目录，`<package-name>` 替换为实际需要安装的包名。

#### Q4：服务器系统版本受限，无法升级到 openEuler 24.03 LTS SP3，怎么办？

**A4**：可尝试在当前系统版本上手动安装所需的软件包和依赖项。由于 openEuler 24.03 LTS 及以上版本均使用内核 6.6 和 Python 3.11，因此只需将 `/etc/os-release` 和 `/etc/openEuler-release` 文件中的版本信息修改为 24.03 LTS SP3 即可。

请注意，此方法需自行准备所需的软件包和依赖项，可能会遇到兼容性问题，建议在测试环境中验证后再应用于生产环境。
