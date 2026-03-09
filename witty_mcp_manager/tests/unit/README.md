# 单元测试

本目录包含 Witty MCP Manager 各核心模块的单元测试，按源码模块结构组织为子目录，所有测试可在本地运行，无需外部依赖。

## 目录结构

```text
tests/unit/
├── __init__.py
├── README.md                              # 本文件
├── test_exceptions.py                     # 顶层 exceptions.py
├── test_real_configs.py                   # 跨模块端到端验证
├── adapters/                              # src/witty_mcp_manager/adapters/
│   ├── test_adapters.py                   #   base.py, stdio.py, sse.py
│   ├── test_admin_mcp.py                  #   Admin MCP SSE 适配器场景
│   └── test_http_adapter.py               #   http.py (StreamableHTTP)
├── cli/                                   # src/witty_mcp_manager/cli/
│   └── test_cli.py                        #   main.py, servers.py, runtime.py, permissions.py
├── config/                                # src/witty_mcp_manager/config/
│   └── test_config.py                     #   config.py
├── diagnostics/                           # src/witty_mcp_manager/diagnostics/
│   └── test_diagnostics.py                #   checker.py, preflight.py
├── ipc/                                   # src/witty_mcp_manager/ipc/
│   ├── test_ipc.py                        #   auth.py, schemas.py, 路由集成
│   ├── test_ipc_routes.py                 #   routes/registry.py, routes/tools.py
│   └── test_ipc_server.py                 #   server.py 生命周期
├── overlay/                               # src/witty_mcp_manager/overlay/
│   └── test_overlay.py                    #   storage.py, resolver.py
├── registry/                              # src/witty_mcp_manager/registry/
│   ├── test_discovery.py                  #   discovery.py
│   ├── test_models.py                     #   models.py
│   └── test_normalizer.py                 #   normalizer.py
├── runtime/                               # src/witty_mcp_manager/runtime/
│   └── test_runtime.py                    #   manager.py, recycle.py
└── security/                              # src/witty_mcp_manager/security/
    ├── test_security.py                   #   allowlist.py, redaction.py, secrets.py
    └── test_secrets_extended.py           #   secrets.py 补充边界测试
```

## 总览

| 子目录 | 文件数 | 行数 | 测试类 | 测试数 | 对应源码模块 |
| --- | ---: | ---: | ---: | ---: | --- |
| `adapters/` | 3 | 756 | 15 | 58 | `adapters/` |
| `cli/` | 1 | 488 | 7 | 47 | `cli/` |
| `config/` | 1 | 211 | 4 | 15 | `config/` |
| `diagnostics/` | 1 | 257 | 2 | 18 | `diagnostics/` |
| `ipc/` | 3 | 1,424 | 27 | 97 | `ipc/` |
| `overlay/` | 1 | 384 | 2 | 18 | `overlay/` |
| `registry/` | 3 | 908 | 17 | 76 | `registry/` |
| `runtime/` | 1 | 403 | 3 | 18 | `runtime/` |
| `security/` | 2 | 493 | 4 | 50 | `security/` |
| _(顶层)_ | 2 | 617 | 19 | 55 | `exceptions.py` + 跨模块 |
| **总计** | **18** | **~5,940** | **~100** | **452** | |

## 运行测试

```bash
cd witty_mcp_manager

# 运行全部单元测试
uv run pytest tests/unit/ -v

# 运行某个模块的全部测试
uv run pytest tests/unit/registry/ -v
uv run pytest tests/unit/ipc/ -v

# 运行单个文件
uv run pytest tests/unit/registry/test_discovery.py -v

# 运行单个测试类
uv run pytest tests/unit/cli/test_cli.py::TestMainApp -v

# 运行单个测试方法
uv run pytest tests/unit/runtime/test_runtime.py::TestSession::test_session_key -v

# 带覆盖率
uv run pytest tests/unit/ --cov=witty_mcp_manager --cov-report=term
```

---

## 各模块测试详情

### adapters/ — STDIO / SSE / HTTP 适配器

不依赖真实进程或网络连接，通过 mock 隔离测试适配器核心逻辑。

#### test_adapters.py（465 行 · 8 类 · 28 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestToolModel` | 3 | Tool 数据模型 |
| `TestToolCallResult` | 4 | 工具调用结果模型 |
| `TestToolsCache` | 2 | 工具缓存 |
| `TestSTDIOAdapter` | 5 | 类型检查、MCP ID、ServerParams 构建 |
| `TestSSEAdapter` | 4 | 类型检查、MCP ID、断开连接 |
| `TestBaseAdapterMethods` | 4 | 缓存 get/set/clear/info |
| `TestAdapterCreation` | 2 | STDIO/SSE 适配器工厂创建 |
| `TestAdapterWithRealConfigs` | 3 | 真实 git_mcp/ccb_mcp 配置、env 合并 |

#### test_admin_mcp.py（213 行 · 6 类 · 21 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestAdminMCPConfigs` | 4 | rag_mcp/mcp_server_mcp 配置结构、SSE 类型 |
| `TestAdminMCPDirectory` | 3 | mock 目录结构、config.json 验证 |
| `TestSSEServerRecord` | 4 | SSE record 的 transport/source/config |
| `TestSSEAdapter` | 2 | 从真实配置创建 SSE 适配器 |
| `TestAdminMCPVsRPMMCP` | 4 | Admin vs RPM MCP 差异对比 |
| `TestAutoApproveAndAutoInstall` | 4 | autoApprove / autoInstall 字段处理 |

#### test_http_adapter.py（78 行 · 1 类 · 9 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestStreamableHTTPAdapter` | 9 | StreamableHTTP 适配器占位实现（所有方法抛出 "not implemented"） |

---

### cli/ — 命令行接口

使用 `typer.testing.CliRunner` 测试 `witty-mcp` 命令行工具。

#### test_cli.py（488 行 · 7 类 · 47 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestMainApp` | 3 | 主命令 `--help`、子命令帮助 |
| `TestServersSubcommand` | 6 | `servers list/enable/disable` 命令 |
| `TestRuntimeSubcommand` | 5 | `runtime status/sessions/kill` 命令 |
| `TestCLIHelperFunctions` | 13 | `_enabled_label`、`_infer_transport`、`_format_duration` 等辅助函数 |
| `TestPermissions` | 12 | `PrivilegeLevel`、`UserIdentity`、`resolve_scope` 权限系统 |
| `TestCLIWithRealConfigs` | 2 | 基于真实配置的 list/info 逻辑 |
| `TestCLIErrorHandling` | 2 | 配置错误和连接错误处理 |

**关键技术**: `@patch` mock daemon 连接、`CliRunner` 模拟终端调用

---

### config/ — 配置管理

#### test_config.py（211 行 · 4 类 · 15 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestAdminSource` | 3 | AdminSource 模型构造与属性 |
| `TestManagerConfig` | 5 | ManagerConfig 默认值、路径解析、嵌套配置 |
| `TestLoadConfig` | 6 | 显式路径 / 环境变量 / 默认路径 / 空文件 / 无效 YAML |
| `TestGetConfigAndReset` | 2 | 单例获取与重置 |

---

### diagnostics/ — 诊断与预检查

#### test_diagnostics.py（257 行 · 2 类 · 18 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestPreflightChecker` | 10 | 命令白名单 (TC003/TC004)、命令存在性、依赖完整性 (TC005)、修复建议 |
| `TestChecker` | 6 | 文件完整性、STDIO 缺 command、传输类型不匹配、配置有效性 |

---

### ipc/ — IPC 接口

全面测试 IPC 模块的认证、数据 Schema、HTTP 路由和服务器生命周期。

#### test_ipc.py（630 行 · 14 类 · 48 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestUserContext` | 4 | 用户上下文创建与属性 |
| `TestValidateUserId` | 2 | 参数化用户 ID 验证 |
| `TestCreateSystemContext` | 2 | 系统上下文创建 |
| `TestGetUserContext` | 3 | 异步用户上下文获取 |
| `TestAPIResponse` | 2 | API 响应模型 |
| `TestServerSummary` | 1 | 服务器摘要字段 |
| `TestToolSchema` | 1 | 工具 Schema 模型 |
| `TestToolCallRequest` | 2 | 工具调用请求模型 |
| `TestToolCallResult` | 2 | 工具调用结果模型 |
| `TestHealthStatus` | 1 | 健康检查 Schema |
| `TestRuntimeStatus` | 1 | 运行时状态 Schema |
| `TestCacheInfo` | 1 | 缓存信息 Schema |
| `TestIPCServerHelpers` | 4 | `determine_server_status`、`calculate_idle_time` |
| `TestIPCServerIntegration` | 7 | FastAPI `TestClient` 完整路由测试 |

**关键技术**: `@pytest.mark.asyncio`、`@pytest.mark.parametrize`、`TestClient`

#### test_ipc_routes.py（517 行 · 8 类 · 30 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestDetermineServerStatusEdgeCases` | 4 | 服务器状态判定边界条件 |
| `TestValidateConfigureRequest` | 4 | configure 请求参数校验 |
| `TestApplyConfigureRequest` | 3 | configure 请求应用逻辑 |
| `TestBuildConfigureResult` | 1 | configure 响应构建 |
| `TestEnsureServerReady` | 5 | 服务器就绪检查 |
| `TestGetCacheInfo` | 3 | 缓存信息获取 |
| `TestIPCServerConfigureEndpoint` | 4 | configure API 端点集成测试 |
| `TestIPCServerClass` | 5 | IPCServer 类属性与初始化 |

#### test_ipc_server.py（277 行 · 5 类 · 19 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestIPCServerStartup` | 3 | 启动流程与依赖注入 |
| `TestIPCServerShutdown` | 5 | 关闭、资源清理、错误处理 |
| `TestIPCServerAdapters` | 7 | 适配器创建/缓存/重启/错误 |
| `TestIPCServerProperties` | 2 | 服务器属性测试 |
| `TestCreateApp` | 1 | `create_app` 工厂函数 |

---

### overlay/ — 覆盖配置层

测试全局/用户级别的配置覆盖存储和多层解析。

#### test_overlay.py（384 行 · 2 类 · 18 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestOverlayStorage` | 11 | 目录创建、全局/用户覆盖 CRUD、启用/禁用状态 |
| `TestOverlayResolver` | 9 | 默认配置、全局/用户覆盖合并、禁用优先级、arg_patches、enabled 列表 |

---

### registry/ — 服务器注册表

#### test_discovery.py（177 行 · 2 类 · 10 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestDiscovery` | 7 | 目录扫描、JSON 解析、RPM 元数据、隐藏目录跳过 |
| `TestDiscoveryAdminSources` | 2 | Admin 来源注册、按 ID 查询 |

**测试用例编号**: TC001（扫描成功）

#### test_models.py（468 行 · 11 类 · 52 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestStdioConfig` | 6 | STDIO 配置构造、验证 |
| `TestSseConfig` | 6 | SSE 配置构造、验证 |
| `TestTimeouts` | 4 | 超时配置 |
| `TestConcurrency` | 4 | 并发配置 |
| `TestToolPolicy` | 2 | 工具策略 |
| `TestNormalizedConfig` | 7 | 归一化配置、computed_field |
| `TestDiagnostics` | 6 | 诊断模型 |
| `TestServerRecord` | 4 | 服务器记录 |
| `TestOverride` | 6 | 覆盖模型 |
| `TestRuntimeState` | 4 | 运行时状态 |
| `TestEnums` | 3 | 枚举值 |

#### test_normalizer.py（263 行 · 4 类 · 14 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestStandardFormatNormalization` | 4 | STDIO/SSE 归一化、传输类型推断、extras 保留 |
| `TestAdminPrivateFormatCompatibility` | 4 | `autoApprove→alwaysAllow` 映射、`mcpType` 传输检测 |
| `TestRealVmConfigs` | 3 | 真实 git_mcp、code_review_assistant、admin rag_mcp |
| `TestEdgeCases` | 4 | 空/缺失 mcpServers、rpm_metadata 集成 |

---

### runtime/ — 运行时管理

#### test_runtime.py（403 行 · 3 类 · 18 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestSession` | 7 | session_key、初始状态、start/stop/touch |
| `TestRuntimeManager` | 7 | 创建/复用/获取/移除/列表/关闭会话、统计 |
| `TestSessionRecycler` | 4 | 启停、空闲回收、活跃保护 |

**关键技术**: `@pytest.mark.asyncio`

---

### security/ — 安全模块

#### test_security.py（329 行 · 3 类 · 31 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestCommandAllowlist` | 9 | 默认/自定义白名单、路径解析、添加/移除/验证 |
| `TestLogRedactor` | 8 | JWT/Bearer token 脱敏、字典/env/headers 脱敏 |
| `TestSecretsManager` | 13 | env/file/secrets 引用解析、CRUD 操作 |

**关键技术**: `@patch("shutil.which")`

#### test_secrets_extended.py（164 行 · 1 类 · 19 测试）

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestSecretsManagerExtended` | 19 | 未知引用类型、文件读取错误、权限错误、嵌套 list 解析、无效 key 名、OS 错误处理 |

---

### 顶层测试文件

#### test_exceptions.py（261 行 · 14 类 · 38 测试）

测试 `witty_mcp_manager.exceptions` 中所有自定义异常的创建、属性和继承层级。

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestWittyMCPError` | 4 | 基类异常 |
| `TestConfigurationError` | 1 | 配置异常 |
| `TestDiscoveryError` | 2 | 发现异常 |
| `TestNormalizationError` | 2 | 归一化异常 |
| `TestDiagnosticsError` | 2 | 诊断异常 |
| `TestAdapterError` | 2 | 适配器异常 |
| `TestSessionError` | 2 | 会话异常 |
| `TestSecurityError` | 2 | 安全异常 |
| `TestCommandNotAllowedError` | 3 | 命令不允许异常 |
| `TestConfigError` | 1 | 配置错误 |
| `TestWittyRuntimeError` | 1 | 运行时错误 |
| `TestToolCallError` | 2 | 工具调用错误 |
| `TestMCPTimeoutError` | 2 | 超时错误 |
| `TestExceptionHierarchy` | 2 | 继承层级验证 |

#### test_real_configs.py（356 行 · 5 类 · 17 测试）

基于 openEuler 24.03 LTS SP3 VM 的真实配置数据进行跨模块端到端验证。

| 测试类 | 测试数 | 描述 |
| --- | ---: | --- |
| `TestRealMCPDiscovery` | 5 | TC101-105：11 服务器基线扫描、command 类型验证 |
| `TestRealMCPNormalizer` | 4 | alwaysAllow、敏感参数、timeout、env+description |
| `TestRealMCPDiagnostics` | 3 | uv/python3 白名单、依赖检测 |
| `TestRealMCPIntegration` | 2 | 完整 discovery + diagnostics 流程 |
| `TestAutoApproveFieldMapping` | 3 | autoApprove→alwaysAllow 字段映射 |

---

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
- `real_*_mcp_config` — 真实 VM 配置数据（git_mcp、ccb_mcp、oedeploy_mcp、cvekit_mcp 等）
- `mock_server_record` / `mock_sse_server_record` — 模拟 ServerRecord
- `mock_admin_mcp_dir` — Admin MCP 目录结构
