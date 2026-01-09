# mcp_center

## 1. Introduction to mcp_center
mcp_center is the mcp registration center for AI assistants. This module mainly includes the following capabilities:

1. Manage mcp-server capabilities
2. Provide the built-in oe-mcp service (primarily for openEuler OS basic capabilities, with a convenient management method)
3. Automatically deploy mcp-server capabilities

```
mcp_center is used to build the mcp capabilities of AI assistants. Its directory structure is as follows:```
├── client Test client
├── config Public and private configuration files
├── mcp_config Configuration files for mcp registration to the framework
├── oe_cli_mcp_server Exclusive mcp service for oe-cli
├── service Collection of system service files (.service)
├── test Test client directory
├── third_party_mcp Directory for third-party server source code
├── util Storage directory for mcp_center's CLI tools
├── README.en.md English version description
├── README.md Chinese version description
└── run.sh Script to start mcp services
```


### Running Instructions

1. Before running the mcp server, execute the following command in the mcp_center directory:
   ```
   export PYTHONPATH=$(pwd)
   ```
2. Start the mcp server through Python for testing
3. You can test each mcp tool through client.py in the client directory. The specific URL, tool name, and input parameters can be adjusted as needed.


## 2. Rules for Adding New mcp
1. **Create Service Source Code Directory**  
   Create a new folder under the `mcp_center/servers` directory. Example (taking top mcp as an example):
   ```
   servers/top/
   ├── README.en.md       English version of mcp service details
   ├── README.md          Chinese version of mcp service details
   ├── requirements.txt   Contains only private installation dependencies  (to avoid conflicts with public dependencies; you are responsible for dependency installation/management, and modify the corresponding Python path in the .service file)
   └── src                Source code directory (including server main entry)
       └── server.py
   ```

2. **Configuration File Settings**  
   Create a new configuration file under the `mcp_center/config/private` directory. Example (taking top mcp as an example):
   ```
   config/private/top
   ├── config_loader.py   Configuration loader (including public configuration and private custom configuration)
   └── config.toml        Private custom configuration
   ```

3. **Update Documentation**
- When adding a new mcp, synchronize its basic information to the existing mcp section in the main directory's README (ensure no port conflicts; ports start from 12100).
- When adding a new mcp, add a corresponding `.service` file in the `service_file` directory of the main directory (to package the mcp as a system service).
- When adding a new mcp, create a directory with the corresponding name in the `mcp_config` directory of the main directory, and create a `config.json` file under it (for registering the mcp to the framework).
- When adding a new mcp, add a command to the `run.sh` script in the main directory (if needed) for deploying the mcp.

**Note**: If the mcp has an independent environment, you can adjust the specific Python environment in the `.service` file to ensure the mcp runs normally.

4. **Remote Command Execution**  
   Currently, this is uniformly handled by the `cmd_executor_tool`; there is no need to develop remote capabilities for each individual mcp.


## 3. Existing MCP Services in mcp_center

| Category | Details                                                                 |
|----------|-------------------------------------------------------------------------|
| Name     | oe-cli-mcp-server                                                       |
| Directory| mcp_center/third_party_mcp/oe_cli_mcp_server                                   |
| Port     | 12555                                                                   |
| Description | Basic operation and maintenance MCP: file management, package management, system info query, process management, command execution, SSH repair, network repair |


| Category | Details                     |
|----------|------------------------------|
| Name     | rag-server                   |
| Directory| mcp_center/third_party_mcp/rag       |
| Port     | 12311                        |
| Description | Lightweight RAG service      |


-----------------

# 2. Introduction to MCPTool

MCPTool is the Tool required for MCP service registration. In this project, Tool is defined as a Tool package to facilitate MCP tool management and parsing. This mode is mainly used for the oe-mcp service.

The purpose of defining this structure has two aspects: on one hand, it makes it easier to manage the built-in oe-mcp capabilities; on the other hand, it provides a more convenient way for new mcp developers to manage MCPTools.

This structure requires little prior knowledge of mcp. You only need to follow the logic of normal Python project development and the guidelines below to enhance the capabilities of oe-mcp.


## 2.1 MCPTool Definition

### 2.1.1 Tool Structure

The basic structure of MCPTool is as follows:

```
.
├── base.py/base_dir # Optional: other helper functions (not required)
├── config.json # Required: configuration file
├── requirements.txt # Dependency file
├── readme.md # Usage documentation (Chinese)
├── readme.en.md # Usage documentation (English)
└── tool.py # Required: core Tool function collection
```


### 2.1.2 File Description

#### tool.py

This file exposes Tool functions for MCP registration. All functions (e.g., `file_tool`, `pkg_tool`) in `tool.py` will be registered to the MCP service. The basic format is as follows:

```python
# tool.py

def file_tool():
   pass

def pkg_tool():
   pass
```

#### config.json

This file records the prompts for the functions in Tool.py provided by this Tool package. A basic example is as follows:

Notes:
The tool name must match the function name (each tool name corresponds to a function in tool.py).
Both Chinese (zh) and English (en) prompts are required.

```json
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

A standard requirements.txt dependency file. When adding the Tool package, this file will be read automatically, and the corresponding dependencies will be installed.

```
requests==2.31.0 
```

#### base.py/base_dir

This file or directory contains helper functions (not exposed for MCP registration). The structure and content can be customized.
#### readme.md/readme.en.md

These files provide usage instructions for the Tool package.

### 2.1 MCPTool Management

#### Adding an MCPTool Package

Prepare an MCPTool.zip file (e.g., test_tools.zip) that meets the basic requirements of the Tool package.
Use the following command to add it:

```
oe-mcp -add test_tools.zip
```

#### Removing an MCPTool Package
1. Use oe-mcp -tool to view the current Tool packages and their included Tool functions.
2. Use the Tool package name obtained from the above step and execute the following command:
```
oe-mcp -remove test_tools
```