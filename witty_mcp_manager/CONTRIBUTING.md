# Witty MCP Manager 贡献指南

本文档面向在 `framework/witty_mcp_manager/` 目录内开发与提交代码的贡献者。

## 开发环境

本项目使用 **uv** 管理虚拟环境与依赖。

- 前提：已安装 uv（见 <https://github.com/astral-sh/uv> ）

在仓库内执行：

- 进入包目录：`cd witty_mcp_manager`
- 安装开发依赖：`uv sync --extra dev`

说明：

- `dev` extra 包含 `pytest/ruff/mypy` 以及类型桩（例如 `types-PyYAML`）。
- 运行质量门禁命令前，默认假设已经安装 `dev` 依赖。

## 质量门禁（提交前必须通过）

建议使用同一套解释器与依赖，统一通过 `uv run ...` 执行：

- 格式化检查：`uv run ruff format --check .`
- 代码检查：`uv run ruff check .`
- 类型检查：`uv run mypy src`
- 单元测试：`uv run pytest -q`

可以一键运行：

- `uv run ruff format --check . && uv run ruff check . && uv run mypy src && uv run pytest -q`

## 测试说明

- 单元测试位于 `tests/unit/`
- 集成测试预留在 `tests/integration/`（需要 VM / 真实 `/opt/mcp-servers/servers` 数据时再补齐）

## 提交规范

- 保持改动最小化：只改与当前需求相关的文件。
- 保持风格一致：遵循 ruff/formatter 输出。
- 如新增/修改 public API，请同步更新 `README.md`（必要时补充测试）。

## 常见问题

### mypy 报 `Library stubs not installed for "yaml"`

请先安装开发依赖：

- `uv sync --extra dev`

然后再执行：

- `uv run mypy src`
