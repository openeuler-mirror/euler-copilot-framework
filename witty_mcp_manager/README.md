# Witty MCP Manager

通用 MCP Host/Loader，用于 Witty 智能助手（openEuler AI 助手）。

## 功能

统一管理三种 MCP 来源：

1. **RPM 生态 MCP**：自动发现 `/opt/mcp-servers/servers`
2. **旧版 master mcp**（oe-cli-mcp-server）：通过 SSE Adapter 连接
3. **独立第三方 MCP Server**：通过配置文件注册

## 安装

### 从 RPM 安装（推荐）

```bash
sudo dnf install witty-mcp-manager
```

### 从源码安装

```bash
cd witty_mcp_manager

# 使用 uv
uv pip install -e .

# 或使用 pip
pip install -e .
```

## 使用

### 启动守护进程

```bash
# 由 systemd 管理
sudo systemctl start witty-mcp-manager

# 或手动启动
witty-mcp daemon
```

### CLI 命令

```bash
# 列出所有 MCP Server
witty-mcp servers list

# 启用/禁用 Server
witty-mcp servers enable <mcp_id>
witty-mcp servers disable <mcp_id>

# 查看 Server 详情
witty-mcp servers inspect <mcp_id>

# 查看运行时状态
witty-mcp runtime status <mcp_id>

# 查看日志
witty-mcp logs
```

## 开发

### 环境准备

```bash
cd witty_mcp_manager

# 创建开发环境并安装依赖
uv sync --extra dev

# 激活环境（可选）
source .venv/bin/activate
```

说明：本项目的静态检查（ruff/mypy）与测试（pytest）默认依赖 `dev` extra。
为了保证使用到的是同一套依赖与解释器，建议所有命令都通过 `uv run ...` 执行。

### 运行测试

```bash
# 运行所有测试
uv run pytest

# 运行单元测试
uv run pytest tests/unit -v

# 运行覆盖率
uv run pytest --cov=witty_mcp_manager --cov-report=html
```

### 代码检查

```bash
# 格式化
uv run ruff format .

# 检查
uv run ruff check .

# 类型检查
uv run mypy src
```

### 质量门禁（推荐一键）

```bash
uv run ruff format --check . \
    && uv run ruff check . \
    && uv run mypy src \
    && uv run pytest -q
```

### 常见问题

- mypy 提示 `Library stubs not installed for "yaml"`

    这通常表示你没有安装 `dev` 依赖。请先执行 `uv sync --extra dev`，再运行 `uv run mypy src`。

### 构建二进制

使用 Nuitka 构建独立二进制文件，无需系统 Python 包：

```bash
# 前置条件 (openEuler / CentOS / Fedora)
sudo dnf install gcc gcc-c++ python3-devel patchelf ccache
pip install nuitka ordered-set

# 构建 onefile 二进制（默认）
./scripts/build-nuitka.sh

# 构建 standalone 目录
./scripts/build-nuitka.sh --mode standalone

# 自定义输出目录
./scripts/build-nuitka.sh --output-dir /opt/witty-mcp

# 清理并重新构建
./scripts/build-nuitka.sh --clean
```

构建产物位于 `dist/witty-mcp`。

## 目录结构

```text
witty_mcp_manager/
├── pyproject.toml              # 项目配置
├── README.md                   # 项目说明
├── scripts/
│   └── build-nuitka.sh         # Nuitka 构建脚本
├── src/
│   └── witty_mcp_manager/      # 源码
│       ├── __init__.py
│       ├── exceptions.py
│       ├── config/             # 配置加载
│       ├── registry/           # 服务发现与注册
│       ├── diagnostics/        # 诊断检查
│       ├── overlay/            # 覆盖配置
│       ├── runtime/            # 会话管理
│       ├── adapters/           # 传输适配器
│       ├── security/           # 安全模块
│       ├── ipc/                # UDS IPC 服务
│       └── cli/                # CLI 命令
├── tests/                      # 测试文件
│   ├── conftest.py
│   ├── unit/                   # 单元测试
│   └── integration/            # 集成测试
└── data/
    └── witty-mcp-manager.service  # systemd 服务文件
```

## 许可证

Mulan PSL v2

## 贡献

欢迎提交 Issue 和 PR 到 [openEuler euler-copilot-framework 仓库](https://atomgit.com/openeuler/euler-copilot-framework)。

开发/提交规范见 `CONTRIBUTING.md`。
