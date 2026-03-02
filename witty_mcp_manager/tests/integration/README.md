# 集成测试

本目录包含 Witty MCP Manager 的完整集成测试套件，需要在 openEuler VM 上运行。

## 测试文件

| 文件 | 测试类 | 测试数 | 描述 |
| --- | --- | --- | --- |
| `test_witty_mcp_manager.py` | 13 | 46 | CLI + IPC 接口测试（daemon 交互） |
| `test_mcp_servers.py` | 4 | 8+ | MCP 服务器直连测试（STDIO/SSE） |

## 测试环境要求

- **操作系统**: openEuler 24.03 LTS SP3 或兼容系统
- **架构**: aarch64 (ARM64)
- **Python**: 3.11+
- **包管理器**: uv
- **服务状态**: witty-mcp-manager daemon 运行中
- **MCP 服务器**: 至少一个 MCP 服务器安装（支持 RPM 和 mcp_center 两种来源）

### 支持的 MCP 服务器来源

| 来源 | 目录 | 配置文件 | 传输协议 | 服务器数 |
| ---- | ---- | -------- | -------- | -------- |
| RPM 安装 | `/opt/mcp-servers/servers/` | `mcp_config.json` | stdio | 10 |
| mcp_center | `/usr/lib/sysagent/mcp_center/mcp_config/` | `config.json` | sse | 2 |

## 运行测试

### 快速开始

```bash
# 设置环境变量启用 VM 测试
export WITTY_TEST_VM=1

# 运行所有测试
uv run pytest tests/integration/test_witty_mcp_manager.py -v

# 使用辅助脚本（自动设置环境变量）
./scripts/run_integration_tests.sh
```

### 运行特定测试

```bash
# 运行特定测试类
WITTY_TEST_VM=1 uv run pytest tests/integration/test_witty_mcp_manager.py::TestIPCHealth -v

# 运行特定测试方法
WITTY_TEST_VM=1 uv run pytest tests/integration/test_witty_mcp_manager.py::TestCLIServers::test_servers_list -v
```

### 生成 HTML 报告

```bash
# 使用辅助脚本
REPORT=1 ./scripts/run_integration_tests.sh

# 或者直接使用 pytest
WITTY_TEST_VM=1 uv run pytest tests/integration/test_witty_mcp_manager.py -v --html=report.html --self-contained-html
```

## 测试套件结构

### IPC 接口测试 (19 个测试)

| 测试类 | 测试方法 | 描述 |
| ------ | -------- | ---- |
| `TestIPCHealth` | `test_health_endpoint` | 测试 /health 端点响应 |
| | `test_health_has_servers` | 验证健康响应包含服务器信息 |
| | `test_health_version_format` | 验证版本号格式 |
| `TestIPCRegistry` | `test_list_servers` | 测试列出服务器 |
| | `test_list_servers_include_disabled` | 测试包含禁用服务器 |
| | `test_server_detail` | 测试获取服务器详情 |
| | `test_server_detail_not_found` | 测试不存在的服务器返回 404 |
| | `test_server_summary_fields` | 验证服务器摘要字段 |
| `TestIPCEnableDisable` | `test_enable_server` | 测试启用服务器 |
| | `test_disable_server` | 测试禁用服务器 |
| | `test_enable_disable_toggle` | 测试启用/禁用切换 |
| | `test_enable_non_existent_server` | 测试启用不存在的服务器 |
| `TestIPCTools` | `test_list_tools` | 测试列出工具 |
| | `test_list_tools_force_refresh` | 测试强制刷新工具列表 |
| | `test_list_tools_disabled_server` | 测试禁用服务器的工具列表 |
| `TestIPCToolCall` | `test_call_tool` | 测试调用工具 |
| `TestIPCRuntime` | `test_list_sessions` | 测试列出会话 |
| | `test_list_sessions_all_users` | 测试列出所有用户会话 |
| | `test_session_detail_not_found` | 测试不存在的会话返回 404 |

### CLI 接口测试 (17 个测试)

| 测试类 | 测试方法 | 描述 |
| ------ | -------- | ---- |
| `TestCLIVersion` | `test_version_command` | 测试 version 命令 |
| | `test_help_command` | 测试 --help 选项 |
| `TestCLIServers` | `test_servers_list` | 测试 servers list 命令 |
| | `test_servers_list_json` | 测试 servers list --json 输出 |
| | `test_servers_list_all` | 测试 servers list --all 选项 |
| | `test_servers_info` | 测试 servers info 命令 |
| | `test_servers_info_not_found` | 测试不存在服务器的 info |
| | `test_servers_tools` | 测试 servers tools 命令 |
| | `test_servers_tools_json` | 测试 servers tools --json 输出 |
| `TestCLIEnableDisable` | `test_servers_enable_user` | 测试 servers enable 命令 |
| | `test_servers_disable_user` | 测试 servers disable 命令 |
| | `test_servers_enable_disable_toggle` | 测试启用/禁用切换 |
| `TestCLIRuntime` | `test_runtime_status` | 测试 runtime status 命令 |
| | `test_runtime_status_json` | 测试 runtime status --json 输出 |
| | `test_runtime_sessions` | 测试 runtime sessions 命令 |
| `TestCLIConfig` | `test_config_show` | 测试 config show 命令 |
| | `test_config_show_json` | 测试 config show --json 输出 |

### 端到端测试 (2 个测试)

| 测试类 | 测试方法 | 描述 |
| ------ | -------- | ---- |
| `TestEndToEnd` | `test_full_workflow_ipc` | 测试完整的 IPC 工作流 |
| | `test_full_workflow_cli` | 测试完整的 CLI 工作流 |

### 并发测试 (2 个测试)

| 测试类 | 测试方法 | 描述 |
| ------ | -------- | ---- |
| `TestConcurrency` | `test_concurrent_health_checks` | 测试并发健康检查 |
| | `test_concurrent_list_servers` | 测试并发列出服务器 |

### 错误处理测试 (4 个测试)

| 测试类 | 测试方法 | 描述 |
| ------ | -------- | ---- |
| `TestErrorHandling` | `test_invalid_endpoint` | 测试访问无效端点 |
| | `test_invalid_method` | 测试无效 HTTP 方法 |
| | `test_invalid_json_body` | 测试无效 JSON 请求体 |
| | `test_missing_user_header` | 测试缺少用户头 |

### 数据收集测试 (2 个测试)

| 测试类 | 测试方法 | 描述 |
| ------ | -------- | ---- |
| `TestDataCollection` | `test_collect_ipc_data` | 收集 IPC 接口数据 |
| | `test_collect_cli_data` | 收集 CLI 输出数据 |

## 环境变量

| 变量 | 默认值 | 描述 |
| ---- | ------ | ---- |
| `WITTY_TEST_VM` | - | 设置为 `1` 启用 VM 测试 |
| `WITTY_CLI` | `witty-mcp` | CLI 命令名称 |
| `WITTY_USE_UV_RUN` | `1` | 设置为 `1` 使用 `uv run witty-mcp` |
| `WITTY_PROJECT_DIR` | - | 项目目录路径 |

## 故障排除

### 测试被跳过

如果所有测试都显示 `SKIPPED`：

- 确保设置了 `WITTY_TEST_VM=1` 环境变量
- 验证 daemon socket 存在：`ls -la /run/witty/mcp-manager.sock`

### enable/disable 测试失败

如果出现权限错误：

```text
PermissionError: [Errno 13] Permission denied: '/var/lib/witty-mcp-manager/overrides/users/...'
```

这通常不会发生（测试使用唯一用户 ID `test_user_<pid>_<timestamp>` 并自动清理）。如果确实遇到，可以运行：

```bash
# 仅在遇到权限错误时需要
sudo chmod 1777 /var/lib/witty-mcp-manager/overrides/users/
```

### CLI 测试失败

如果 CLI 命令找不到：

- 确保 `WITTY_USE_UV_RUN=1`（默认启用）
- 或者将 `witty-mcp` 添加到 PATH

### 工具列表测试失败

如果 `servers tools` 测试失败并显示 "SERVER_DISABLED"：

- 这是预期行为，测试会自动在查询工具前启用服务器
- 确保有至少一个 ready 状态的 MCP 服务器

## 在其他 VM 上运行

要在其他 openEuler 24.03 LTS SP3 虚拟机上运行测试：

1. 克隆代码仓库
2. 安装 uv: `sudo dnf install uv`
3. 同步依赖: `uv sync --extra dev`
4. 确保 daemon 运行: `sudo systemctl start witty-mcp-manager`
5. 运行测试: `./scripts/run_integration_tests.sh`

## 测试设计说明

### 唯一测试用户 ID

测试使用唯一的用户 ID 格式：`test_user_<pid>_<timestamp>`，这样设计的原因：

1. **避免权限冲突**: 如果之前的 daemon 以 root 运行并创建了测试用户目录，新的测试以普通用户运行时会因权限问题失败
2. **隔离测试**: 每次测试运行都使用独立的用户身份，不会相互干扰
3. **自动清理**: 测试结束后自动清理创建的目录，测试脚本启动时也会清理旧目录

### 测试清理机制

- **测试结束清理**: `test_config` fixture 在 teardown 时删除测试用户的 override 目录
- **脚本启动清理**: `run_integration_tests.sh` 在前置检查时清理所有 `test_user_*` 目录

## 添加新测试

新测试应该：

1. 使用 `@skip_unless_vm` 装饰器
2. 使用提供的 fixtures（`ipc_client`, `system_client`, `test_config` 等）
3. 遵循现有的命名约定
4. 添加适当的文档字符串

---

## test_mcp_servers.py — MCP 服务器直连测试

该文件直接使用 MCP Python SDK 连接真实 MCP 服务器，不经过 witty-mcp-manager daemon。

### 测试类

| 测试类 | 测试数 | 描述 |
| --- | --- | --- |
| `TestStdioMCPConnection` | 10（参数化） | STDIO 模式连接 10 个 RPM MCP 服务器 |
| `TestSSEMCPConnection` | 2（参数化） | SSE 模式连接 2 个 mcp_center 服务器 |
| `TestMCPTools` | 4 | 工具调用验证（network/code_search/sys_info/rag） |
| `TestDataCollection` | 2 | 收集 STDIO/SSE MCP 元数据为 JSON |

### 运行方式

```bash
# 在 VM 上运行全部 MCP 服务器测试
uv run pytest tests/integration/test_mcp_servers.py -v

# 仅运行连接测试
uv run pytest tests/integration/test_mcp_servers.py::TestStdioMCPConnection -v

# 仅运行工具调用测试
uv run pytest tests/integration/test_mcp_servers.py::TestMCPTools -v
```

### 覆盖的 MCP 服务器

**STDIO 模式（10 个）**:
api_document_mcp、code_review_assistant、code_search_mcp、cvekit_mcp、git_mcp、network_manager_mcp、mcp-oedp、oeGitExt_mcp、rpm-builder_mcp、ccbMcp

**SSE 模式（2 个）**:
oe_cli_mcp（`http://127.0.0.1:12555/sse`）、rag_mcp（`http://127.0.0.1:12311/sse`）

### 已知预期失败

| MCP 服务器 | 原因 | 缺少参数 |
| --- | --- | --- |
| mcp-oedp | 需要 DeepSeek API | `--model_url`、`--api_key`、`--model_name` |
| ccbMcp | 需要 EulerMaker 完整配置 | 17 个参数（Gitee 凭证、网关等） |

---

## 相关文档

- [测试套件总览](../README.md)
- [单元测试](../unit/README.md)
