# Witty MCP Manager 测试套件

本目录包含 Witty MCP Manager 的完整测试套件，涵盖单元测试、适配器测试和集成测试。

## 目录结构

```text
tests/
├── README.md               # 本文件
├── __init__.py
├── conftest.py              # 全局共享 fixtures
├── unit/                    # 单元测试
│   ├── README.md
│   ├── test_adapters.py     # 适配器深度测试
│   ├── test_admin_mcp.py    # Admin MCP 私有格式测试
│   ├── test_cli.py          # CLI 命令行接口测试
│   ├── test_diagnostics.py  # 诊断与预检查测试
│   ├── test_discovery.py    # MCP 服务器发现测试
│   ├── test_ipc.py          # IPC 接口测试
│   ├── test_normalizer.py   # 配置归一化测试
│   ├── test_overlay.py      # 覆盖配置层测试
│   ├── test_real_configs.py # 真实 VM 配置测试
│   ├── test_runtime.py      # 运行时管理测试
│   └── test_security.py     # 安全模块测试
├── adapters/                # 适配器公共 API 测试
│   └── test_adapters.py     # 模块导出与数据类测试
└── integration/             # 集成测试（需 VM 环境）
    ├── README.md
    ├── test_mcp_servers.py  # MCP 服务器直连测试
    └── test_witty_mcp_manager.py  # CLI + IPC 完整测试
```

## 测试统计

| 测试分类 | 文件数 | 测试类数 | 测试方法数 | 备注 |
| --- | --- | --- | --- | --- |
| 单元测试 (`unit/`) | 12 | ~55 | ~213 | 本地可运行，无外部依赖 |
| 适配器测试 (`adapters/`) | 1 | 8 | 17 | 模块公共 API 验证 |
| 集成测试 (`integration/`) | 2 | 17 | ~54 | 需要 VM 环境 + MCP 服务器 |
| **总计** | **15** | **~80** | **~284** | |

## 快速开始

### 环境准备

```bash
cd witty_mcp_manager

# 安装开发依赖
uv sync --extra dev
```

### 运行单元测试

```bash
# 运行所有单元测试（无需外部依赖）
uv run pytest tests/unit/ -v

# 运行适配器公共 API 测试
uv run pytest tests/adapters/ -v

# 运行所有本地测试
uv run pytest tests/unit/ tests/adapters/ -v
```

### 运行集成测试

集成测试需要在 openEuler 24.03 LTS SP3 VM 上运行，详见 [integration/README.md](integration/README.md)。

```bash
# 在 VM 环境中运行
export WITTY_TEST_VM=1
uv run pytest tests/integration/ -v

# 或使用辅助脚本
./scripts/run_integration_tests.sh
```

### 带覆盖率运行

```bash
# 全量覆盖率
uv run pytest --cov=witty_mcp_manager --cov-report=html --cov-report=term

# 仅单元测试覆盖率
uv run pytest tests/unit/ --cov=witty_mcp_manager --cov-report=html
```

## 测试框架与依赖

| 依赖 | 版本 | 用途 |
| --- | --- | --- |
| pytest | ≥9.0.2 | 测试框架 |
| pytest-asyncio | ≥1.3.0 | 异步测试支持 |
| pytest-cov | ≥7.0.0 | 覆盖率报告 |

配置位于 [pyproject.toml](../pyproject.toml)：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-v --tb=short"
```

## 全局 Fixtures（conftest.py）

[conftest.py](conftest.py) 提供所有测试共享的 fixtures，分为以下几类：

### 1. 标准格式 Fixtures（`sample_*`）

符合 [Claude Desktop / Cline 事实标准](https://docs.cline.bot/mcp/configuring-mcp-servers) 的 MCP 配置。

| Fixture | 描述 |
| --- | --- |
| `sample_stdio_config` | 标准 STDIO 配置 |
| `sample_sse_config` | 标准 SSE 配置 |
| `sample_mcp_config` | 完整 mcp_config.json |
| `sample_mcp_rpm_yaml` | RPM 元数据 YAML |

### 2. Admin 私有格式 Fixtures（`admin_*`）

euler-copilot-framework mcp_center 特有的配置格式（使用 `autoApprove` 而非 `alwaysAllow`）。

| Fixture | 描述 |
| --- | --- |
| `admin_sse_config` | Admin SSE 配置 |
| `real_rag_mcp_config` | RAG 知识库真实配置 |
| `real_mcp_server_mcp_config` | MCP Server 真实配置 |

### 3. 真实 VM Fixtures（`real_*`）

来自 openEuler 24.03 LTS SP3 测试 VM 的真实配置数据。

| Fixture | 对应 MCP 服务器 |
| --- | --- |
| `real_git_mcp_config` | Git 操作工具 |
| `real_ccb_mcp_config` | EulerMaker 构建系统 |
| `real_oedeploy_mcp_config` | oeDeploy 部署工具 |
| `real_cvekit_mcp_config` | CVE 补丁处理 |
| `real_code_review_assistant_mcp_config` | 代码审查助手 |
| `real_api_document_mcp_config` | API 文档生成 |
| `real_network_manager_mcp_config` | 网络管理 |

### 4. Mock 基础设施 Fixtures

| Fixture | 描述 |
| --- | --- |
| `mock_mcp_servers_dir` | 模拟 RPM MCP 服务器目录 |
| `mock_real_mcp_servers_dir` | 模拟真实 VM 目录结构 |
| `mock_admin_mcp_dir` | 模拟 Admin MCP 目录 |
| `mock_state_directory` | 模拟状态目录 |
| `mock_config` / `mock_real_config` | 模拟配置对象 |
| `mock_server_record` | 模拟 ServerRecord |

## 覆盖率要求

| 模块 | 最低覆盖率 |
| --- | --- |
| 核心模块（registry、runtime、adapters） | 90% |
| IPC / API 层 | 85% |
| CLI | 70% |
| 工具类 | 80% |
| **总体** | **80%** |

## 测试命名约定

- **测试文件**: `test_<module>.py`
- **测试类**: `Test<Class>` 或 `Test<Feature>`
- **测试方法**: `test_<what>_<condition>_<expected>`

示例：

```text
test_scan_empty_directory_returns_empty_list
test_parse_invalid_json_raises_error
test_connect_with_valid_config_succeeds
```

## 调试测试

```bash
# 详细输出
uv run pytest -vv

# 显示 print 语句
uv run pytest -s

# 失败时进入调试器
uv run pytest --pdb

# 仅运行上次失败的测试
uv run pytest --lf

# 运行单个测试
uv run pytest tests/unit/test_discovery.py::TestDiscovery::test_scan_servers_success -v
```

## 添加新测试

1. 在对应目录下创建 `test_<module>.py`
2. 使用 `conftest.py` 中的共享 fixtures
3. 异步测试使用 `@pytest.mark.asyncio` 装饰器（如果未使用全局 `asyncio_mode = "auto"`）
4. 参数化测试使用 `@pytest.mark.parametrize`
5. 集成测试添加 `@skip_unless_vm` 装饰器
6. 确保测试可独立运行，不依赖执行顺序

## 相关文档

- [单元测试 README](unit/README.md)
- [集成测试 README](integration/README.md)
