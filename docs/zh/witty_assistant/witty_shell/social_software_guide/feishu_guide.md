# 飞书连接openCode部署教程

# 一、概述

本部署教程旨在将openCode与飞书进行连接，以实现飞书内的智能助手功能。通过以下步骤，您将能够在飞书中使用openCode提供的智能服务，核心依赖飞书CLI工具（飞书开放平台命令行工具）、openCode-bridge桥接器及相关基础环境，确保各组件正常联动。

# 二、安装步骤

## 1. 前提条件

- 已有飞书企业账号，并具备管理员权限（需开放飞书开放平台相关权限，部分操作需组织认证账号）。

- 已安装Node.js环境（建议版本20.18.2及以上，与后续npm安装依赖兼容）。

- 已安装openCode-bridge（参考[openCode Bridge 桥接器安装教程](./bridge_introduce.md)）。

- 已安装openCode和Witty Assistant，并完成基础部署（参考[Witty Assistant 安装教程](../deploy_guide/deployment.md)）。

## 2. 安装飞书CLI（选装，推荐安装）

飞书CLI是面向飞书开放平台的命令行工具，专为人类与AI智能体打造，涵盖消息、云文档、多维表格等核心业务领域，提供200+命令及19项AI智能体技能，安装后可更便捷地进行应用管理、权限配置等操作，助力openCode与飞书的高效集成。

### 步骤2.1 下载并安装飞书CLI

执行以下命令安装：

```sh
# 无需配置失效镜像，直接通过国内npm源安装飞书CLI
npm install -g @larksuite/cli --registry=https://registry.npmmirror.com

# 安装 CLI SKILL（必需，依赖GitCode镜像仓库，该仓库为飞书CLI官方仓库的实时镜像，用于加速访问）
npx skills add https://gitcode.com/gh_mirrors/cli414/cli.git -y -g
```

### 步骤2.2 登录飞书应用并获取密钥

```sh
# 初始化飞书CLI配置
lark-cli config init

# 登录飞书账号（推荐方式）
lark-cli auth login --recommend
```

执行上述命令后，将引导您登录飞书账号，登录成功后，系统会自动在飞书开放平台的“企业自建应用”中创建一个新应用，并生成App ID和App Secret，**请妥善保存这两个信息**，后续配置openCode-bridge时需用到。

图示指引：

![飞书CLI机器人](./pictures/飞书CLI机器人.png)

![获取App ID和App Secret](./pictures/获取飞书CLI机器人的App_ID和App_Secrect.png)

Tip：很多权限（如群聊、私聊相关操作权限）需要组织认证账号才会开放，若操作中提示权限不足，请确认飞书账号已完成组织认证。

## 3. 通过openCode-bridge配置飞书

1. 进入openCode-bridge配置中心，依次点击「平台接入」→「配置飞书」；

2. 在配置页面中，填写步骤2.2中获取的App ID和App Secret；

3. 点击「保存配置」，完成飞书与openCode-bridge的关联。

图示指引：

![填写飞书CLI获取的App ID和App Secret](./pictures/填写飞书CLI机器人的App_ID和App_Serect.png)

配置完成后，重启openCode-bridge服务，使配置生效：

```sh
cd openCode-bridge
./scripts/start.sh
```

## 4. 验证连接

1. 在飞书中创建一个新的群聊；

2. 邀请步骤2.2中创建的飞书CLI机器人加入该群聊；

3. 在群聊中发送消息，观察是否能够触发openCode的智能助手功能，若能正常响应，则说明连接成功。

图示指引：

![使用飞书CLI机器人](./pictures/使用飞书CLI机器人.png)

# 三、常见问题说明

- 若npm安装失败：检查Node.js版本是否达标，可尝试清除npm缓存（`npm cache clean -f`）后重新安装，确保[npm mirror](https://registry.npmmirror.com)源可正常访问。

- 若CLI SKILL安装失败：检查网络是否能访问GitCode镜像仓库，该仓库为实时同步镜像，若仍无法访问，可直接访问[飞书CLI官方仓库](https://github.com/larksuite/cli)获取相关资源。

- 若连接验证失败：确认App ID和App Secret填写正确，openCode-bridge服务已重启，飞书机器人已加入群聊且账号具备对应权限。
