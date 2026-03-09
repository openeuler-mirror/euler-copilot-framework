# Witty MCP Manager 测试环境管理指南

## 快速开始

### 两种模式选择

**开发模式**（推荐用于本地开发）：使用 `uv run`，当前用户运行
**生产模式**：需要系统安装，使用 `witty-mcp` 系统用户

详见：[开发模式 vs 生产模式对比](DEV_VS_PROD_MODE.md)

### 1. 首次设置（开发模式 - 推荐）

```bash
# 进入 witty_mcp_manager 目录
cd witty_mcp_manager

# 配置本地开发环境
./scripts/test_env.sh setup-dev

# 安装开发服务
./scripts/test_env.sh install-dev

# 启动服务（需要 DEV_MODE=true）
DEV_MODE=true ./scripts/test_env.sh start
```

### 1. 首次设置（生产模式）

```bash
# 1. 构建二进制（必须）
cd witty_mcp_manager
./scripts/build_nuitka.sh

# 2. 安装二进制
sudo cp dist/witty-mcp /usr/bin/witty-mcp
sudo chmod 755 /usr/bin/witty-mcp

# 3. 验证二进制
/usr/bin/witty-mcp --version

# 4. 安装生产服务
./scripts/test_env.sh install

# 5. 启动服务
./scripts/test_env.sh start
```

### 2. 验证安装

```bash
# 健康检查
./scripts/test_env.sh health

# 查看服务状态
./scripts/test_env.sh status

# 查看日志
./scripts/test_env.sh logs
```

---

## 常用命令

### 开发环境

```bash
# 使用 uv 配置开发依赖 (运行测试、代码检查等)
./scripts/test_env.sh setup-dev
```

### 服务管理

```bash
# 生产模式
./scripts/test_env.sh start
./scripts/test_env.sh stop
./scripts/test_env.sh restart
./scripts/test_env.sh status

# 开发模式（需要 DEV_MODE=true）
DEV_MODE=true ./scripts/test_env.sh start
DEV_MODE=true ./scripts/test_env.sh stop
DEV_MODE=true ./scripts/test_env.sh restart
DEV_MODE=true ./scripts/test_env.sh status

# 💡 提示：设置别名简化开发模式命令
alias wmm-dev='DEV_MODE=true ./scripts/test_env.sh'
# 然后使用: wmm-dev start, wmm-dev status, etc.
```

### 日志查看

```bash
# 查看最近 100 行日志 (默认)
./scripts/test_env.sh logs

# 查看最近 50 行日志
./scripts/test_env.sh logs 50

# 跟随查看日志 (实时)
./scripts/test_env.sh logs-f

# 跟随查看最近 200 行
./scripts/test_env.sh logs-f 200
```

### 测试

```bash
# 列出所有 MCP 服务器（优先通过 daemon，回退目录扫描）
./scripts/test_env.sh test-mcps

# 用 mcp-cli 逐个 ping 所有服务器
./scripts/test_env.sh test-mcps ping-all

# ping 单个服务器
./scripts/test_env.sh test-mcps ping git_mcp

# 查看服务器的工具列表 (JSON 输出)
./scripts/test_env.sh test-mcps tools cvekit_mcp

# 通过 daemon 调用工具
./scripts/test_env.sh test-mcps call git_mcp git_status '{"repo_path":"/tmp"}'

# 查看 test-mcps 子命令帮助
./scripts/test_env.sh test-mcps help

# 健康检查
./scripts/test_env.sh health
```

### 清理

```bash
# 清理状态和配置文件 (保留服务)
./scripts/test_env.sh clean

# 完全清理 (包括卸载服务)
./scripts/test_env.sh clean-all
```

---

## 环境变量

可以通过环境变量自定义配置：

```bash
# 使用自定义 MCP 服务器路径
MCP_SERVERS_PATH=/custom/path ./scripts/test_env.sh test-mcps

# 使用自定义状态目录
STATE_DIR=/var/lib/custom-witty ./scripts/test_env.sh status
```

支持的环境变量：

| 变量名 | 默认值 | 说明 |
| ------ | ------ | ---- |
| `DEV_MODE` | `false` | 开发模式标志 (true/false) |
| `MCP_SERVERS_PATH` | `/opt/mcp-servers/servers` | RPM MCP 服务器安装路径 |
| `MCP_CENTER_PATH` | `/usr/lib/sysagent/mcp_center/mcp_config` | mcp_center MCP 配置路径 |
| `STATE_DIR` | `/var/lib/witty-mcp-manager` | 状态目录 |
| `RUNTIME_DIR` | `/run/witty` | 运行时目录 |
| `CONFIG_DIR` | `/etc/witty` | 配置目录 |
| `WITTY_USER` | `test-user` | daemon 查询用户 |

---

## 典型工作流

### 开发调试流程（开发模式）

```bash
# 1. 设置开发环境
./scripts/test_env.sh setup-dev
./scripts/test_env.sh install-dev

# 2. 在本地开发和测试
cd witty_mcp_manager
uv run pytest -v

# 3. 代码修改后重启服务
DEV_MODE=true ./scripts/test_env.sh restart

# 4. 查看日志确认
DEV_MODE=true ./scripts/test_env.sh logs-f
```

### 开发调试流程（生产模式）

```bash
# 1. 在本地开发和测试
cd witty_mcp_manager
uv run pytest -v

# 2. 重新构建二进制
./scripts/build_nuitka.sh

# 3. 安装新的二进制
sudo cp dist/witty-mcp /usr/bin/witty-mcp

# 4. 重启服务
./scripts/test_env.sh restart

# 5. 查看日志确认
./scripts/test_env.sh logs-f
```

### 问题排查流程

```bash
# 1. 查看服务状态
./scripts/test_env.sh status

# 2. 查看日志
./scripts/test_env.sh logs 200

# 3. 健康检查
./scripts/test_env.sh health

# 4. 如果需要，重启服务
./scripts/test_env.sh restart

# 5. 发现 MCP 服务器
./scripts/test_env.sh test-mcps
```

### 清理重新开始

```bash
# 1. 停止服务
./scripts/test_env.sh stop

# 2. 清理状态
./scripts/test_env.sh clean

# 3. 重新启动
./scripts/test_env.sh start

# 如果需要完全重置
./scripts/test_env.sh clean-all
./scripts/test_env.sh install
./scripts/test_env.sh start
```

---

## 脚本功能详解

### setup-dev

配置本地开发环境，包括：

- 检查 uv 是否安装
- 使用 `uv sync` 同步所有依赖
- 验证安装成功
- 提示后续质量检查命令

### deploy

部署到测试 VM，包括：

- 创建 `witty-mcp` 系统用户
- 创建必要的目录结构
- 设置正确的权限
- 安装 systemd 服务文件
- 启用服务 (但不启动)

### start/stop/restart

标准的 systemd 服务管理命令：

- `start`: 启动服务并显示状态
- `stop`: 停止服务
- `restart`: 重启服务并显示状态

### status

显示 systemd 服务状态，包括：

- 运行状态 (active/inactive)
- 进程 PID
- 内存使用
- 最近的日志条目

### logs

查看 journald 日志：

- 默认显示最近 100 行
- 可指定行数
- 支持跟随模式 (`logs-f`) 实时查看

### clean

清理测试数据，包括：

- 停止服务 (如果运行中)
- 清理 overrides 目录
- 清理 cache 目录
- 清理 runtime 目录
- 清理 UDS 套接字
- 重建目录结构和权限

**注意**: 会提示确认，不会删除服务文件。

### clean-all

完全清理，包括：

- 停止并禁用服务
- 删除 systemd 服务文件
- 删除所有目录 (state/runtime/config)
- 重载 systemd

**注意**: 会提示确认，需要重新运行 `deploy` 才能使用。

### test-mcps

MCP 服务器测试套件，支持多个子命令：

| 子命令 | 说明 | 查询方式 |
| ------ | ---- | -------- |
| `test-mcps [list]` | 列出所有服务器状态 | daemon UDS / 目录扫描 |
| `test-mcps ping-all` | 逐个 ping 测试 | mcp-cli 直连 |
| `test-mcps ping <server>` | ping 单个服务器 | mcp-cli 直连 |
| `test-mcps tools <server>` | 查看工具列表 (JSON) | daemon UDS / mcp-cli |
| `test-mcps call <server> <tool> [args]` | 调用工具 | daemon UDS |
| `test-mcps help` | 子命令帮助 | - |

**查询优先级**: `list`、`tools`、`call` 优先通过 daemon UDS socket 查询，如果 daemon 未运行则回退。`ping` / `ping-all` 始终使用 mcp-cli 直连 MCP 服务器。

**前置条件**: `ping` / `ping-all` 需要安装 mcp-cli (`uv tool install mcp-cli`; 安装后如不在 PATH 中，请运行 `uv tool update-shell` 或手动更新 PATH).

### health

全面健康检查，包括：

- ✓ SSH 连接
- ✓ 服务状态
- ✓ UDS 套接字存在
- ✓ 目录权限
- ⚠ MCP 服务器路径

输出清晰的通过/失败状态。

---

## 故障排除

### 服务启动失败

```bash
# 查看详细日志
./scripts/test_env.sh logs 500

# 检查目录权限
sudo ls -la /var/lib/witty-mcp-manager
sudo ls -la /run/witty

# 检查服务用户
id witty-mcp

# 手动测试服务
sudo -u witty-mcp /usr/bin/witty-mcp daemon
```

### MCP 测试失败

```bash
# 列出服务器状态（通过 daemon 或目录扫描）
./scripts/test_env.sh test-mcps

# 用 mcp-cli ping 测试单个服务器
./scripts/test_env.sh test-mcps ping git_mcp

# 查看服务器的工具列表
./scripts/test_env.sh test-mcps tools cvekit_mcp

# 通过 daemon 调用工具测试
./scripts/test_env.sh test-mcps call git_mcp git_status '{"repo_path":"/tmp"}'

# 检查 MCP 服务器路径
ls -la /opt/mcp-servers/servers

# 通过 daemon 直接查询 (curl)
curl -s --unix-socket /run/witty/mcp-manager.sock \
  -H "X-Witty-User: test-user" \
  http://localhost/v1/servers | python3 -m json.tool
```

### 权限问题

```bash
# 检查服务文件权限
sudo systemctl cat witty-mcp-manager

# 修复目录权限
sudo chown -R witty-mcp:witty-mcp /var/lib/witty-mcp-manager
sudo chown -R witty-mcp:witty-mcp /run/witty

# 重启服务
./scripts/test_env.sh restart
```

### 服务无响应

```bash
# 检查服务状态
systemctl status witty-mcp-manager

# 检查进程
ps aux | grep witty-mcp

# 检查 UDS 套接字
ls -la /run/witty/*.sock

# 强制重启
sudo systemctl stop witty-mcp-manager
sudo pkill -9 witty-mcp
./scripts/test_env.sh start
```

### uv 未安装

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 验证安装
uv --version
```

---

## 最佳实践

1. **首次使用**: 始终从 `setup-dev` 开始
2. **安装后**: 运行 `health` 检查确保一切正常
3. **查看日志**: 使用 `logs-f` 实时监控启动过程
4. **发现 MCP**: 安装后运行 `test-mcps` 发现服务器
5. **遇到问题**: 先运行 `health` 然后查看 `logs`
6. **重新开始**: 使用 `clean` 而不是 `clean-all`（除非确实需要）
7. **权限要求**: 大部分命令需要 root 或 sudo 权限

---

## 帮助信息

查看完整帮助：

```bash
./scripts/test_env.sh help
```

或不带参数运行：

```bash
./scripts/test_env.sh
```

---
