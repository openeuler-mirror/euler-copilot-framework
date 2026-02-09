# Witty MCP Manager: 开发模式 vs 生产模式

## 概述

`test_env.sh` 脚本现在支持两种安装模式，以适应不同的使用场景。

## 两种模式对比

| 特性 | 开发模式 (`install-dev`) | 生产模式 (`install`) |
| ---- | ---------------------- | ----------------- |
| **服务名称** | `witty-mcp-manager-dev` | `witty-mcp-manager` |
| **启动方式** | `uv run witty-mcp daemon` | `/usr/bin/witty-mcp daemon` |
| **运行用户** | 当前用户 (安装时自动检测) | `witty-mcp` 系统用户 |
| **工作目录** | 项目根目录 | 无特定要求 |
| **前置要求** | `uv sync` 完成 | **Nuitka 构建的二进制** (`/usr/bin/witty-mcp`) |
| **安装方式** | uv 管理依赖 | 使用 Nuitka 构建 |
| **适用场景** | 本地开发、调试 | 生产部署、测试服务器 |
| **安全限制** | 较宽松 (方便调试) | 较严格 (systemd hardening) |

### 资源占用对比

| 指标 | 开发模式 | 生产模式 | 说明 |
| ---- | ------- | ------- | ---- |
| **内存占用** | ~80M | ~180M | 生产模式使用 Nuitka onefile,需要解压依赖到内存 |
| **磁盘占用** | 项目源码 (~10MB) + `.venv` (~100MB) | 二进制文件 (~27MB) | 生产模式无需完整 Python 环境 |
| **启动时间** | ~1-2s | ~1s | 两者启动速度相近 |
| **CPU 占用** | 正常 | 正常 | 运行时 CPU 占用相近 |

**内存差异说明**:

- **开发模式** (~80M): 使用系统 Python + venv,按需加载依赖
- **生产模式** (~180M): Nuitka onefile 打包所有依赖,运行时解压到内存

**如需减少生产模式内存占用**, 可使用 `--mode standalone` 构建:

```bash
./scripts/build_nuitka.sh --mode standalone
```

Standalone 模式将依赖提取到目录,内存占用可降至 ~100M,但需要分发整个目录。

## 使用指南

### 开发模式工作流

```bash
# 1. 配置开发环境
cd /path/to/euler-copilot/framework/witty_mcp_manager
./scripts/test_env.sh setup-dev

# 2. 安装开发服务
./scripts/test_env.sh install-dev

# 3. 管理服务 (需要 DEV_MODE=true)
DEV_MODE=true ./scripts/test_env.sh start
DEV_MODE=true ./scripts/test_env.sh status
DEV_MODE=true ./scripts/test_env.sh logs
DEV_MODE=true ./scripts/test_env.sh restart
DEV_MODE=true ./scripts/test_env.sh stop

# 4. 测试 MCP
DEV_MODE=true ./scripts/test_env.sh test-mcps
```

**提示**: 可以在 `.bashrc` 中设置别名以简化命令：

```bash
alias wmm-dev='DEV_MODE=true /path/to/witty_mcp_manager/scripts/test_env.sh'
# 然后使用: wmm-dev start, wmm-dev status, etc.
```

### 生产模式工作流

```bash
# 1. 构建二进制 (必须使用 Nuitka)
cd /path/to/euler-copilot/framework/witty_mcp_manager
./scripts/build_nuitka.sh

# 2. 安装二进制到系统
sudo cp dist/witty-mcp /usr/bin/witty-mcp
sudo chmod 755 /usr/bin/witty-mcp

# 3. 验证二进制
/usr/bin/witty-mcp --version

# 4. 安装生产服务
./scripts/test_env.sh install

# 5. 管理服务
./scripts/test_env.sh start
./scripts/test_env.sh status
./scripts/test_env.sh logs
./scripts/test_env.sh restart
./scripts/test_env.sh stop

# 6. 测试 MCP
./scripts/test_env.sh test-mcps
```

## 技术细节

### 开发模式服务文件

开发模式使用 `data/witty-mcp-manager-dev.service` 模板，安装时会替换以下占位符：

- `PROJECT_ROOT` → 项目根目录绝对路径
- `INSTALL_USER` → 当前用户名
- `INSTALL_GROUP` → 当前用户组

生成的服务文件示例：

```ini
[Service]
Type=simple
WorkingDirectory=/home/user/euler-copilot/framework/witty_mcp_manager
ExecStart=/usr/bin/env bash -c 'cd /home/user/euler-copilot/framework/witty_mcp_manager && uv run witty-mcp daemon'
User=user
Group=user
```

### 生产模式服务文件

生产模式直接使用 `data/witty-mcp-manager.service`，假设程序已安装：

```ini
[Service]
Type=simple
ExecStart=/usr/bin/witty-mcp daemon
User=witty-mcp
Group=witty-mcp
```

## 常见问题

### Q: 可以同时安装两种模式吗？

A: 可以！两种模式使用不同的服务名称，互不干扰。

```bash
# 同时安装
./scripts/test_env.sh install-dev
./scripts/test_env.sh install

# 同时运行
DEV_MODE=true ./scripts/test_env.sh start
./scripts/test_env.sh start

# 查看状态
DEV_MODE=true ./scripts/test_env.sh status
./scripts/test_env.sh status
```

### Q: 开发模式下忘记设置 DEV_MODE=true 会怎样？

A: 会操作生产服务而不是开发服务。建议：

1. 设置 shell 别名
2. 或者在开发环境的 `.bashrc` 中 export DEV_MODE=true

### Q: 如何在开发模式和生产模式之间切换？

A: 只需要停止当前服务，启动另一个：

```bash
# 从生产切换到开发
./scripts/test_env.sh stop
DEV_MODE=true ./scripts/test_env.sh start

# 从开发切换到生产
DEV_MODE=true ./scripts/test_env.sh stop
./scripts/test_env.sh start
```

### Q: 清理时会删除哪些服务？

A: `clean-all` 会清理所有服务（开发和生产）：

```bash
./scripts/test_env.sh clean-all
# 会停止并删除:
# - witty-mcp-manager
# - witty-mcp-manager-dev
```

### Q: 开发模式为什么使用当前用户而不是 witty-mcp？

A: 便于开发和调试：

- 可以直接编辑代码，无需 sudo
- 日志和状态文件权限更简单
- 更容易使用 IDE 调试器附加到进程

### Q: 生产环境可以使用开发模式吗？

A: 不推荐，原因：

- 开发模式安全限制较宽松
- 依赖项目目录结构存在
- 没有使用专用的系统用户
- 不适合作为系统服务长期运行

但对于测试服务器或临时部署是可以的。

## 环境变量参考

| 变量 | 用途 | 默认值 |
| ---- | ---- | ----- |
| `DEV_MODE` | 切换开发/生产服务 | `false` |
| `MCP_SERVERS_PATH` | RPM MCP 服务器路径 | `/opt/mcp-servers/servers` |
| `MCP_CENTER_PATH` | mcp_center 配置路径 | `/usr/lib/sysagent/mcp_center/mcp_config` |
| `STATE_DIR` | 状态目录 | `/var/lib/witty-mcp-manager` |
| `RUNTIME_DIR` | UDS socket 目录 | `/run/witty` |
| `CONFIG_DIR` | 配置目录 | `/etc/witty` |
| `WITTY_USER` | daemon 查询用户 | `test-user` |

## 相关文档

- [测试环境使用指南](../scripts/reference/test_env/TEST_ENV_GUIDE.md)
- [使用示例](../scripts/reference/test_env/EXAMPLES.md)
