# 单元测试

本目录包含 Witty MCP Manager 各核心模块的单元测试，所有测试可在本地运行，无需外部依赖。

## 测试文件概览

| 文件 | 行数 | 测试类 | 测试数 | 测试对象 |
| --- | --- | --- | --- | --- |
| `test_cli.py` | 488 | 7 | 36 | CLI 命令行接口与权限系统 |
| `test_discovery.py` | 176 | 2 | 10 | MCP 服务器目录扫描与配置解析 |
| `test_ipc.py` | 630 | 12 | 32 | IPC 认证、Schema、路由 |
| `test_runtime.py` | 403 | 3 | 14 | 会话生命周期与回收机制 |
| `test_security.py` | 325 | 3 | 25 | 命令白名单、日志脱敏、密钥管理 |
| `test_overlay.py` | 378 | 2 | 17 | 覆盖配置层存储与解析 |
| `test_normalizer.py` | 261 | 4 | 13 | 配置格式归一化转换 |
| `test_diagnostics.py` | 257 | 2 | 13 | 预检查与完整性验证 |
| `test_adapters.py` | 465 | 8 | 25 | STDIO/SSE 适配器深度测试 |
| `test_admin_mcp.py` | 213 | 5 | 13 | Admin MCP 私有格式配置 |
| `test_real_configs.py` | 356 | 5 | 15 | 真实 VM 配置端到端验证 |
| **总计** | **~3,950** | **~53** | **~213** | |

## 运行测试

```bash
cd witty_mcp_manager

# 运行全部单元测试
uv run pytest tests/unit/ -v

# 运行单个文件
uv run pytest tests/unit/test_discovery.py -v

# 运行单个测试类
uv run pytest tests/unit/test_cli.py::TestMainApp -v

# 运行单个测试方法
uv run pytest tests/unit/test_runtime.py::TestSession::test_session_key -v

# 带覆盖率
uv run pytest tests/unit/ --cov=witty_mcp_manager --cov-report=term
```

## 各模块测试详情

### test_cli.py — CLI 命令行接口

使用 `typer.testing.CliRunner` 测试 `witty-mcp` 命令行工具。

| 测试类 | 测试数 | 描述 |
| --- | --- | --- |
| `TestMainApp` | 3 | 主命令 `--help`、子命令帮助 |
| `TestServersSubcommand` | 5 | `servers list/enable/disable` 命令 |
| `TestRuntimeSubcommand` | 5 | `runtime status/sessions/kill` 命令 |
| `TestCLIHelperFunctions` | 12 | `_enabled_label`、`_infer_transport`、`_format_duration` 等辅助函数 |
| `TestPermissions` | 12 | `PrivilegeLevel`、`UserIdentity`、`resolve_scope` 权限系统 |
| `TestCLIWithRealConfigs` | 2 | 基于真实配置的 list/info 逻辑 |
| `TestCLIErrorHandling` | 2 | 配置错误和连接错误处理 |

**关键技术**: `@patch` mock daemon 连接、`CliRunner` 模拟终端调用

---

### test_discovery.py — MCP 服务器发现

测试 MCP 服务器目录扫描和 `mcp_config.json` / `rpm_metadata.yaml` 解析。

| 测试类 | 测试数 | 描述 |
| --- | --- | --- |
| `TestDiscovery` | 8 | 目录扫描、JSON 解析、RPM 元数据、隐藏目录跳过 |
| `TestDiscoveryAdminSources` | 2 | Admin 来源注册、按 ID 查询 |

**测试用例编号**: TC001（扫描成功）

---

### test_ipc.py — IPC 接口

全面测试 IPC 模块的认证、数据 Schema 和 HTTP 路由。

| 测试类 | 测试数 | 描述 |
| --- | --- | --- |
| `TestUserContext` | 4 | 用户上下文创建与属性 |
| `TestValidateUserId` | 2 | 参数化用户 ID 验证 |
| `TestCreateSystemContext` | 2 | 系统上下文创建 |
| `TestGetUserContext` | 3 | 异步用户上下文获取 |
| `TestAPIResponse` | 2 | API 响应模型 |
| `TestServerSummary` | 1 | 服务器摘要字段 |
| `TestToolSchema` / `TestToolCallRequest` / `TestToolCallResult` | 5 | 工具相关 Schema |
| `TestIPCServerHelpers` | 4 | `determine_server_status`、`calculate_idle_time` |
| `TestIPCServerIntegration` | 8 | FastAPI `TestClient` 完整路由测试 |

**关键技术**: `@pytest.mark.asyncio`、`@pytest.mark.parametrize`、`TestClient`

---

### test_runtime.py — 运行时管理

测试 MCP 会话的生命周期管理和空闲会话回收机制。

| 测试类 | 测试数 | 描述 |
| --- | --- | --- |
| `TestSession` | 7 | session_key、初始状态、start/stop/touch |
| `TestRuntimeManager` | 7 | 创建/复用/获取/移除/列表/关闭会话 |
| `TestSessionRecycler` | 4 | 启停、空闲回收、活跃保护 |

**关键技术**: `@pytest.mark.asyncio`

---

### test_security.py — 安全模块

测试命令执行白名单、敏感信息脱敏和密钥管理。

| 测试类 | 测试数 | 描述 |
| --- | --- | --- |
| `TestCommandAllowlist` | 11 | 默认/自定义白名单、路径解析、添加/移除/验证 |
| `TestLogRedactor` | 8 | JWT/Bearer token 脱敏、字典/env/headers 脱敏 |
| `TestSecretsManager` | 9 | env/file/secrets 引用解析、CRUD 操作 |

**关键技术**: `@patch("shutil.which")`

---

### test_overlay.py — 覆盖配置层

测试全局/用户级别的配置覆盖存储和多层解析。

| 测试类 | 测试数 | 描述 |
| --- | --- | --- |
| `TestOverlayStorage` | 11 | 目录创建、全局/用户覆盖 CRUD、启用/禁用状态 |
| `TestOverlayResolver` | 7 | 默认配置、全局/用户覆盖合并、禁用优先级、arg_patches |

---

### test_normalizer.py — 配置归一化

测试标准格式（Claude Desktop / Cline）与 Admin 私有格式之间的转换。

| 测试类 | 测试数 | 描述 |
| --- | --- | --- |
| `TestStandardFormatNormalization` | 4 | STDIO/SSE 归一化、传输类型推断、extras 保留 |
| `TestAdminPrivateFormatCompatibility` | 4 | `autoApprove→alwaysAllow` 映射、`mcpType` 传输检测 |
| `TestRealVmConfigs` | 3 | 真实 git_mcp、code_review_assistant、admin rag_mcp |
| `TestEdgeCases` | 3 | 空/缺失 mcpServers、rpm_metadata 集成 |

---

### test_diagnostics.py — 诊断模块

测试启动前预检查和配置完整性验证。

| 测试类 | 测试数 | 描述 |
| --- | --- | --- |
| `TestPreflightChecker` | 10 | 命令白名单 (TC003/TC004)、命令存在性、依赖完整性 (TC005) |
| `TestChecker` | 5 | 文件完整性、STDIO 缺 command、传输类型不匹配 |

---

### test_adapters.py — STDIO/SSE 适配器

对适配器进行深度单元测试，不依赖真实进程或网络连接。

| 测试类 | 测试数 | 描述 |
| --- | --- | --- |
| `TestToolModel` | 4 | Tool 数据模型 |
| `TestToolCallResult` | 4 | 工具调用结果模型 |
| `TestToolsCache` | 2 | 工具缓存 |
| `TestSTDIOAdapter` | 6 | 类型检查、MCP ID、ServerParams 构建 |
| `TestSSEAdapter` | 4 | 类型检查、MCP ID、断开连接 |
| `TestBaseAdapterMethods` | 4 | 缓存 get/set/clear/info |
| `TestAdapterCreation` | 2 | STDIO/SSE 适配器工厂创建 |
| `TestAdapterWithRealConfigs` | 3 | 真实 git_mcp/ccb_mcp 配置、env 合并 |

---

### test_admin_mcp.py — Admin MCP 配置

测试 witty-framework-lite mcp_center 的私有配置格式。

| 测试类 | 测试数 | 描述 |
| --- | --- | --- |
| `TestAdminMCPConfigs` | 4 | rag_mcp/mcp_server_mcp 配置结构、SSE 类型 |
| `TestAdminMCPDirectory` | 3 | mock 目录结构、config.json 验证 |
| `TestSSEServerRecord` | 4 | SSE record 的 transport/source/config |
| `TestSSEAdapter` | 2 | 从真实配置创建 SSE 适配器 |
| `TestAdminMCPVsRPMMCP` | 3 | Admin vs RPM MCP 差异对比 |

---

### test_real_configs.py — 真实 VM 配置

基于 openEuler 24.03 LTS SP3 VM 的真实配置数据进行端到端单元测试。

| 测试类 | 测试数 | 描述 |
| --- | --- | --- |
| `TestRealMCPDiscovery` | 5 | TC101-TC105：11 服务器基线扫描、command 类型验证 |
| `TestRealMCPNormalizer` | 4 | alwaysAllow、敏感参数、timeout、env+description |
| `TestRealMCPDiagnostics` | 3 | uv/python3 白名单、依赖检测 |
| `TestRealMCPIntegration` | 2 | 完整 discovery + diagnostics 流程 |
| `TestAutoApproveFieldMapping` | 3 | autoApprove→alwaysAllow 字段映射 |

## Mocking 策略

单元测试通过 mock 隔离外部依赖，常用模式：

```python
# Mock 文件系统
@pytest.fixture
def mock_filesystem(self, tmp_path):
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    (test_dir / "config.json").write_text('{"key": "value"}')
    return tmp_path

# Mock 外部命令
@patch("shutil.which", return_value="/usr/bin/uv")
def test_command_exists(mock_which):
    ...

# Mock 异步操作
@pytest.mark.asyncio
async def test_async_op():
    mock_adapter = AsyncMock()
    mock_adapter.connect.return_value = Mock(id="session_123")
    ...
```

## 与 conftest.py 的关系

所有单元测试共享 [tests/conftest.py](../conftest.py) 中的 fixtures。常用的有：

- `sample_stdio_config` / `sample_sse_config` — 标准格式测试数据
- `mock_mcp_servers_dir` / `mock_real_mcp_servers_dir` — 模拟目录结构
- `mock_config` / `mock_real_config` — 模拟配置对象
- `real_*_mcp_config` — 真实 VM 配置数据
- `mock_server_record` — 模拟 ServerRecord
