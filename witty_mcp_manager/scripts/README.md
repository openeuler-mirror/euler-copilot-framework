# Scripts 目录说明

此目录包含 Witty MCP Manager 的各类脚本和工具。

## 📁 目录结构

```text
scripts/
├── README.md                          # 本文件
├── test_env.sh                        # 测试环境管理脚本
├── build_nuitka.sh                    # Nuitka 构建脚本
├── run_integration_tests.sh           # 集成测试脚本
├── generate_openapi.py                # OpenAPI 文档生成脚本
└── reference/                         # 参考文档
    └── test_env/                      # test_env.sh 相关文档
        ├── TEST_ENV_GUIDE.md          # 详细使用指南
        ├── EXAMPLES.md                # 使用示例集
        └── QUICK_REFERENCE.sh         # 快速参考卡片
```

---

## 🚀 主要脚本

### [test_env.sh](test_env.sh) ⭐

Linux 测试环境一站式管理工具

**适用环境：**

- openEuler 24.03 LTS SP3 (或其他 Linux)
- 在 Linux 本地直接执行，无需远程连接
- 需要 root 权限或 sudo 权限

**功能：**

- ✅ 使用 uv 配置开发依赖
- ✅ 安装和配置守护进程
- ✅ 启动/停止/重启守护进程
- ✅ 查看日志和状态
- ✅ 清理配置文件
- ✅ 测试 MCP 服务器（支持双路径扫描：RPM + mcp_center）
- ✅ 健康检查

**核心特性：**

- 自动扫描两个 MCP 安装路径：
  - `/opt/mcp-servers/servers` (RPM MCP)
  - `/usr/lib/sysagent/mcp_center/mcp_config` (mcp_center MCP)
- 支持 daemon 模式查询和回退到目录扫描
- 兼容 `mcp_config.json` 和 `config.json` 两种配置格式

**快速开始：**

```bash
# 在 witty_mcp_manager 目录下执行
./scripts/test_env.sh help           # 查看帮助
./scripts/test_env.sh setup-dev      # 配置开发环境 (uv)
./scripts/test_env.sh install        # 安装服务到系统
./scripts/test_env.sh start          # 启动服务
./scripts/test_env.sh test-mcps      # 测试 MCP（自动扫描 RPM + mcp_center）
./scripts/test_env.sh health         # 健康检查
```

**详细文档：** [reference/test_env/TEST_ENV_GUIDE.md](reference/test_env/TEST_ENV_GUIDE.md)

---

### [build_nuitka.sh](build_nuitka.sh)

**Nuitka 构建脚本** - 构建独立二进制文件

**功能：**

- 使用 Nuitka 编译 Python 代码
- 支持 onefile 和 standalone 模式
- 无需系统 Python 包依赖

**使用：**

```bash
./scripts/build_nuitka.sh                      # 默认 onefile
./scripts/build_nuitka.sh --mode standalone    # standalone 模式
./scripts/build_nuitka.sh --clean              # 清理重建
```

---

### [run_integration_tests.sh](run_integration_tests.sh)

**集成测试脚本** - 运行集成测试套件

**使用：**

```bash
./scripts/run_integration_tests.sh
```

---

### [generate_openapi.py](generate_openapi.py)

**OpenAPI 文档生成工具** - 自动生成 API 文档

**适用环境：**

- 开发环境（需要 Python 3.11+ 和 uv）
- 文档更新时使用

**功能：**

- ✅ 从 FastAPI 应用自动生成 OpenAPI 3.1 规范
- ✅ 支持 JSON 和 YAML 输出格式
- ✅ 输出到文件或 stdout
- ✅ 包含完整的 API 端点、参数、响应定义
- ✅ 自动提取 Pydantic 数据模型

**核心特性：**

- 基于实际代码生成，确保文档与实现同步
- 支持所有 API 端点：Health、Registry、Tools、Runtime
- 包含请求/响应示例和数据模型定义
- 生成的文档可用于 Swagger UI、ReDoc 等工具

**快速开始：**

```bash
# 在 witty_mcp_manager 目录下执行
uv run python scripts/generate_openapi.py                    # 输出到 stdout
uv run python scripts/generate_openapi.py --output docs/openapi.json    # 生成 JSON
uv run python scripts/generate_openapi.py --format yaml --output docs/openapi.yaml  # 生成 YAML
```

**使用场景：**

- API 实现变更后更新文档
- 生成客户端代码的基础
- API 测试和验证
- 文档网站自动生成

---

## 📚 参考文档

### test_env.sh 相关文档

所有文档位于 [reference/test_env/](reference/test_env/) 目录：

#### [TEST_ENV_GUIDE.md](reference/test_env/TEST_ENV_GUIDE.md) 📖

**详细使用指南** - test_env.sh 完整文档

包含：

- 快速开始指南
- 所有命令详解
- 环境变量配置
- 典型工作流
- 故障排除
- 最佳实践

**适合：** 第一次使用或需要了解细节时阅读

---

#### [EXAMPLES.md](reference/test_env/EXAMPLES.md) 📚

**实际使用示例** - 10+ 真实场景演示

包含：

- 完整的首次安装流程
- 日常开发调试
- 问题排查示例
- 测试特定 MCP 服务器
- 查看不同类型的日志
- 清理和重置操作
- CI/CD 自动化示例
- 常见使用模式
- 故障排除速查表

**适合：** 遇到具体场景时查找对应的示例

---

#### [QUICK_REFERENCE.sh](reference/test_env/QUICK_REFERENCE.sh) 📝

**快速参考卡片** - 放在终端边上

包含：

- 首次设置流程
- 最常用命令
- 自定义配置示例
- 问题排查流程
- 开发调试循环
- 提示和技巧

**适合：** 日常工作时快速查找命令

---

## 🎯 新手快速开始

如果你是第一次使用，按以下顺序阅读：

### 1. 5 分钟上手

```bash
./scripts/test_env.sh help
```

查看基本命令，然后直接开始使用

### 2. 10 分钟入门

阅读 [reference/test_env/QUICK_REFERENCE.sh](reference/test_env/QUICK_REFERENCE.sh)

快速浏览常用命令和使用模式

### 3. 30 分钟精通

阅读 [reference/test_env/TEST_ENV_GUIDE.md](reference/test_env/TEST_ENV_GUIDE.md)

详细了解所有功能和配置选项

### 4. 遇到问题时

查看 [reference/test_env/EXAMPLES.md](reference/test_env/EXAMPLES.md)

查找类似的使用场景和解决方案

---

## 📋 常见任务速查

| 任务 | 命令 | 文档 |
| ---- | ---- | ---- |
| 首次配置 | `./scripts/test_env.sh setup-dev` | [TEST_ENV_GUIDE.md](reference/test_env/TEST_ENV_GUIDE.md) |
| 安装服务 | `./scripts/test_env.sh install` | [TEST_ENV_GUIDE.md](reference/test_env/TEST_ENV_GUIDE.md) |
| 启动服务 | `./scripts/test_env.sh start` | [TEST_ENV_GUIDE.md](reference/test_env/TEST_ENV_GUIDE.md) |
| 查看日志 | `./scripts/test_env.sh logs-f` | [TEST_ENV_GUIDE.md](reference/test_env/TEST_ENV_GUIDE.md) |
| 健康检查 | `./scripts/test_env.sh health` | [TEST_ENV_GUIDE.md](reference/test_env/TEST_ENV_GUIDE.md) |
| 测试 MCP | `./scripts/test_env.sh test-mcps` | [TEST_ENV_GUIDE.md](reference/test_env/TEST_ENV_GUIDE.md) |
| 清理状态 | `./scripts/test_env.sh clean` | [TEST_ENV_GUIDE.md](reference/test_env/TEST_ENV_GUIDE.md) |
| 问题排查 | 见故障排除流程 | [EXAMPLES.md](reference/test_env/EXAMPLES.md) |
| 构建二进制 | `./scripts/build_nuitka.sh` | [../README.md](../README.md) |

---

## 💡 使用建议

### 日常使用

- [reference/test_env/QUICK_REFERENCE.sh](reference/test_env/QUICK_REFERENCE.sh) - 打印或在另一个终端窗口打开

### 遇到问题时

1. 先运行：`./scripts/test_env.sh health`
2. 然后查看：[reference/test_env/EXAMPLES.md](reference/test_env/EXAMPLES.md) 中的故障排除示例
3. 如果需要详细说明：[reference/test_env/TEST_ENV_GUIDE.md](reference/test_env/TEST_ENV_GUIDE.md) 中的故障排除章节

### 学习新功能

- 按照 [reference/test_env/EXAMPLES.md](reference/test_env/EXAMPLES.md) 中的示例实际操作一遍

---

## 🔧 环境要求

### test_env.sh 要求

**操作系统：**

- openEuler 24.03 LTS SP3 (推荐)

**权限：**

- root 权限或 sudo 权限 (必需)

**前提条件：**

- 本仓库已克隆到本地
- MCP 服务器已安装 (可选，test-mcps 命令需要)
  - **RPM MCP**：通过 dnf 安装到 `/opt/mcp-servers/servers`
  - **mcp_center MCP**：部署到 `/usr/lib/sysagent/mcp_center/mcp_config`
  - 支持部分安装，脚本会自动适配可用的路径

**环境变量：**

- `MCP_SERVERS_PATH`：RPM MCP 安装路径（默认：`/opt/mcp-servers/servers`）
- `MCP_CENTER_PATH`：mcp_center MCP 路径（默认：`/usr/lib/sysagent/mcp_center/mcp_config`）
- 详细配置见 [reference/test_env/TEST_ENV_GUIDE.md](reference/test_env/TEST_ENV_GUIDE.md)

---

## 反馈和贡献

如有问题或建议，请：

1. 查看 [reference/test_env/TEST_ENV_GUIDE.md](reference/test_env/TEST_ENV_GUIDE.md) 的故障排除章节
2. 查看 [reference/test_env/EXAMPLES.md](reference/test_env/EXAMPLES.md) 寻找类似场景
3. 向项目维护者反馈

---

最后更新：2026-02-11
