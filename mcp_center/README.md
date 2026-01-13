# mcp_center

## 1、mcp_center介绍
mcp_center是AI助手的mcp注册中心，该模块主要包含以下能力：

1. 管理mcp-server能力
2. 提供内置的oe-mcp服务，主要服务于openEuler OS的基础能力，并提供便捷的管理方式
3. 自动部署mcp-server能力

mcp_center 用于构建 AI 助手的 mcp 的能力，其目录结构如下：

```
├── client 测试用客户端
├── config 公共和私有配置文件
├── mcp_config mcp注册到框架的配置文件
├── oe_cli_mcp_server oe-cli专属mcp服务
├── service 的service系统服务文件集合
├── test 测试客户端目录
├── third_party_mcp 第三方的server源码所在目录
├── util mcp_center的cli工具存放目录
├── README.en.md 英文版本说明
├── README.md 中文版本说明
└── run.sh 唤起mcp服务的脚本
```

### 运行说明

1. 运行 mcp server 前，需在 mcp_center 目录下执行：
   ```
   export PYTHONPATH=$(pwd)
   ```
2. 通过 Python 唤起 mcp server 进行测试
3. 可通过 test 目录下的 client.py 对每个 mcp 工具进行测试，具体的 URL、工具名称和入参可自行调整

## 2、新增 mcp 规则

1. **创建服务源码目录**  
   在 `mcp_center/servers` 目录下新建文件夹，示例（以 top mcp 为例）：
   ```
   servers/top/
   ├── README.en.md       英文版本的 mcp 服务详情描述
   ├── README.md          中文版本的 mcp 服务详情描述
   ├── requirements.txt   仅包含私有安装依赖（避免与公共依赖冲突，同时自己负责依赖安装和管理，并在service文件做出对应python的修改）
   └── src                源码目录（含 server 主入口）
       └── server.py
   ```

2. **配置文件设置**  
   在 `mcp_center/config/private` 目录下新建配置文件，示例（以 top mcp 为例）：
   ```
   config/private/top
   ├── config_loader.py   配置加载器（含公共配置和私有自定义配置）
   └── config.toml        私有自定义配置
   ```

3. **文档更新**  
   每新增一个 mcp，需在主目录的 README 中现有 mcp 板块同步新增该 mcp 的基本信息（确保端口不冲突，端口从 12100 开始）<br>
   每新增一个 mcp，需要在主目录中的 service_file 中增加.service文件用于将mcp制作成服务<br>
   每新增一个 mcp，需要在主目录中的 mcp_config 中新建对应名称的目录并在下面创建一个config.json（用于将mcp注册到框架）<br>
   每新增一个 mcp，需要在主目录中的 run.sh 中增加一条命令用于部署mcp的脚本（如有需要）

**注意**： 当mcp有独立的环境时，mcp可以在.service中调整具体运行的python环境，保证mcp的正常运行

4. **远程命令执行**  
   当前统一通过cmd_executor_tool工具来完成，无需对每一个mcp开发远程能力


## 3、mcp_center现有的 MCP 服务

| 类别   | 详情                                                   |
|--------|------------------------------------------------------|
| 名称   | oe-cli-mcp-server                                    |
| 目录   | mcp_center/third_party_mcp/oe_cli_mcp_server                 |
| 占用端口 | 12555                                                |
| 简介   | 基础运维MCP：文件管理，软件包管理，系统信息查询，进程管理，命令行执行，ssh修复，network修复 |


| 类别   | 详情                     |
|--------|------------------------|
| 名称   | rag-server             |
| 目录   | mcp_center/third_party_mcp/rag |
| 占用端口 | 12311                  |
| 简介   | 轻量化rag服务               |

-----------------

# 2. MCPTool介绍

MCPTool是MCP服务所需要注册的Tool工具，本项目的将Tool定义为Tool包的形式方便MCP的tool管理和解析。并且该模式主要应用于oe-mcp服务。

定义该结构的目的主要是有两个方面，一方面是可以更加方便的管理内置的oe-mcp的能力，另一方面是为mcp陌生开发者提供更便捷管理mcptool的能力。
本结构几乎无需对mcp有过多了解，只需要按照正常开发python项目的逻辑即可，并按照下文引导即可增强oe-mcp的能力。

## 2.1 MCPTool定义

### 2.1.1 Tool结构

MCPTool的基本结构如下：

```
.
├── base.py/base_dir # 其他函数（不一定需要）
├── config.json #配置文件（必要文件）
├── requirements.txt #依赖文件
├── readme.md
├── readme.en.md
└── tool.py #核心tool函数集合（必要文件）

```

### 2.1.2 文件说明

#### tool.py

主要暴露给MCP注册的tool函数，会将tool.py里所有函数（file_tool和pkg_tool）都注册到MCP服务中，基本形式如下：

```
# tool.py

def file_tool():
    pass

def pkg_tool():
    pass
```

#### config.json

该文件主要是记录本Tool包所提供的Tool.py中函数的提示词，基本样例如下

注意事项：

1.工具名称需和函数名称保持一致，每个tool名称对应的为tool.py中的函数名

2.需要包含zh和en双语的提示词

```
# config.json

{
  "tools": {
    "file_tool": {
      "zh": "",
      "en": ""
    },
    "pkg_tool": {
      "zh": "",
      "en": ""
    }
  }
}
```

#### requirements.txt

标准的requirements.txt依赖文件，添加tool包时会自动读取该文件并安装对应依赖。

```
requests==2.31.0 
```

#### base.py/base_dir

该文件或目录主要为该tool包非暴露给MCP注册的函数，结构以及内容自定义即可。

#### readme.md/readme.en.md

主要提供该tool包的使用说明

### 2.1 MCPTool管理

#### MCPTool包添加

1. 准备一个MCPTool.zip文件，例如test_tools.zip，该zip需要满足tool包的基本要求
2. 使用以下命令即可添加

```sh
oe-mcp -add test_tools.zip
```

#### MCPTool包删除

1. 使用oe-mcp -tool查看当前的tool包以及包含的tool函数

2.通过查看到的tool包名，执行下面命令即可

```sh
oe-mcp -remove test_tools
```




