# Witty MCP Manager 测试环境使用示例

## 示例 1：完整的首次安装流程

```bash
# 场景：第一次配置测试环境（在 Linux 本地执行）

# 步骤 1：进入项目目录
cd /path/to/euler-copilot/framework/witty_mcp_manager

# 步骤 2：配置开发环境
./scripts/test_env.sh setup-dev
# 输出：
# [INFO] 配置本地开发环境...
# [INFO] 使用 uv 同步依赖...
# [SUCCESS] 开发环境配置完成

# 步骤 3：安装服务到系统
./scripts/test_env.sh install
# 输出：
# [INFO] 安装 Witty MCP Manager 服务...
# [INFO] 创建 witty-mcp 用户...
# [INFO] 创建目录结构...
# [INFO] 安装 systemd 服务...
# [SUCCESS] 服务安装完成

# 步骤 4：启动服务
./scripts/test_env.sh start
# 输出：
# [INFO] 启动守护进程...
# [INFO] 检查服务状态...
# ● witty-mcp-manager.service - Witty MCP Manager
#    Active: active (running)

# 步骤 5：验证安装
./scripts/test_env.sh health
# 输出：
# [SUCCESS] ✓ 服务运行中
# [SUCCESS] ✓ UDS 套接字存在
# [SUCCESS] ✓ 状态目录权限正常
# [SUCCESS] ============================================
# [SUCCESS] 健康检查通过 ✓
```

---

## 示例 2：日常开发调试

```bash
# 场景：修改了代码，需要验证

# 1. 查看当前服务状态
./scripts/test_env.sh status

# 2. 重启服务以应用更改（如果二进制已更新）
./scripts/test_env.sh restart

# 3. 实时查看日志，观察启动过程
./scripts/test_env.sh logs-f
# 按 Ctrl+C 退出

# 4. 测试 MCP 服务器
./scripts/test_env.sh test-mcps
# 输出（daemon 运行时）:
# [INFO] 通过 daemon (UDS) 查询 MCP 服务器...
#   ✓ cvekit_mcp                [rpm   ] ready
#   ⚠ git_mcp                   [rpm   ] degraded     - 缺少系统依赖: python3-mcp
#   共 12 个服务器: 1 ready, 9 degraded, 2 unavailable

# 5. 用 mcp-cli ping 测试服务器
./scripts/test_env.sh test-mcps ping cvekit_mcp

# 6. 查看服务器工具列表
./scripts/test_env.sh test-mcps tools cvekit_mcp
```

---

## 示例 3：问题排查

```bash
# 场景：服务启动失败或行为异常

# 步骤 1：健康检查
./scripts/test_env.sh health
# 输出会显示哪些检查失败

# 步骤 2：查看详细日志
./scripts/test_env.sh logs 500
# 查看最近 500 行日志，寻找错误信息

# 步骤 3：如果发现配置问题，清理状态
./scripts/test_env.sh clean
# 确认提示后会清理所有状态文件

# 步骤 4：重新启动
./scripts/test_env.sh start

# 步骤 5：再次检查
./scripts/test_env.sh health
```

---

## 示例 4：测试 MCP 服务器

```bash
# 场景：需要测试 MCP 服务器

# 方式 1：列出所有服务器状态
./scripts/test_env.sh test-mcps

# 方式 2：用 mcp-cli 逐个 ping 所有服务器
./scripts/test_env.sh test-mcps ping-all
# 输出：
#   cvekit_mcp                     ✓ OK
#   git_mcp                        ✓ OK
#   network_manager_mcp            ✗ FAIL
#   结果: 10 个测试, 8 通过, 2 失败

# 方式 3：查看特定服务器的工具列表 (JSON 输出)
./scripts/test_env.sh test-mcps tools cvekit_mcp
# 输出 JSON 格式的工具定义

# 方式 4：通过 daemon 直接调用工具 (需要 daemon 运行)
./scripts/test_env.sh test-mcps call git_mcp git_status '{"repo_path":"/opt/mcp-servers/servers/git_mcp"}'
# 输出 JSON 格式的工具调用结果

# 方式 5：直接用 curl 访问 daemon API
curl -s --unix-socket /run/witty/mcp-manager.sock \
  -H "X-Witty-User: test-user" \
  http://localhost/v1/servers | python3 -m json.tool
```

---

## 示例 5：查看不同类型的日志

```bash
# 查看最近 50 行日志
./scripts/test_env.sh logs 50

# 实时跟随日志（适合观察启动过程）
./scripts/test_env.sh logs-f

# 实时跟随最近 200 行
./scripts/test_env.sh logs-f 200

# 直接使用 journalctl（更多控制）
sudo journalctl -u witty-mcp-manager -f
sudo journalctl -u witty-mcp-manager --since "10 minutes ago"
sudo journalctl -u witty-mcp-manager -p err  # 只看错误
```

---

## 示例 6：清理和重置

```bash
# 场景 1：清理状态文件但保留服务
./scripts/test_env.sh clean
# 提示：确认清理 /var/lib/witty-mcp-manager? (y/N) y
# 会清理：overrides, cache, runtime 目录

# 场景 2：完全清理（包括删除服务）
./scripts/test_env.sh clean-all
# 提示：确认完全清理? 这将删除所有配置和服务。(y/N) y
# 会删除：服务文件、所有目录、状态数据

# 清理后重新安装
./scripts/test_env.sh install
./scripts/test_env.sh start
```

---

## 示例 7：自定义配置路径

```bash
# 场景：使用非标准的目录结构

export MCP_SERVERS_PATH=/custom/mcp/path
export STATE_DIR=/var/lib/custom-witty
export RUNTIME_DIR=/run/custom-witty

./scripts/test_env.sh install
./scripts/test_env.sh start
./scripts/test_env.sh health
```

---

## 示例 8：开发迭代循环

```bash
# 完整的开发-测试-验证循环

# 1. 修改代码
vim src/witty_mcp_manager/runtime/session.py

# 2. 本地测试
cd witty_mcp_manager
uv run pytest tests/unit/test_session.py -v

# 3. 代码质量检查
uv run ruff format . && uv run ruff check . && uv run mypy src

# 4. 重启服务以应用更改（假设已构建新二进制）
./scripts/test_env.sh restart

# 5. 观察运行情况
./scripts/test_env.sh logs-f

# 6. 测试 MCP 集成
./scripts/test_env.sh test-mcps
```

---

## 示例 9：CI/CD 中使用（自动化脚本）

```bash
#!/bin/bash
# CI/CD 自动化测试脚本示例

set -e

cd witty_mcp_manager

# 1. 设置开发环境
./scripts/test_env.sh setup-dev

# 2. 运行本地测试
uv run pytest -v

# 3. 代码质量检查
uv run ruff format --check .
uv run ruff check .
uv run mypy src

# 4. 安装服务（在测试环境）
./scripts/test_env.sh install

# 5. 启动服务
./scripts/test_env.sh start

# 6. 等待服务就绪
sleep 5

# 7. 健康检查 (包括 MCP 发现)
./scripts/test_env.sh health
./scripts/test_env.sh test-mcps

# 8. 清理
./scripts/test_env.sh clean-all

echo "✅ CI/CD 测试通过"
```

---

## 常见使用模式总结

### 快速验证模式（每天多次）

```bash
./scripts/test_env.sh restart && ./scripts/test_env.sh logs-f
```

### 完整验证模式（发布前）

```bash
./scripts/test_env.sh health && \
./scripts/test_env.sh test-mcps && \
./scripts/test_env.sh test-mcps ping-all && \
./scripts/test_env.sh logs 100
```

### 问题排查模式（出现异常时）

```bash
./scripts/test_env.sh health
./scripts/test_env.sh logs 500
./scripts/test_env.sh clean
./scripts/test_env.sh restart
```

### 全新安装模式（新环境）

```bash
./scripts/test_env.sh setup-dev && \
./scripts/test_env.sh install && \
./scripts/test_env.sh start && \
./scripts/test_env.sh health
```

---

## 提示和技巧

1. **使用 `logs-f` 观察启动**：启动服务后立即运行 `logs-f` 可以实时看到初始化过程
2. **健康检查先行**：遇到问题时，先运行 `health` 可以快速定位问题区域
3. **清理状态而非完全清理**：大多数情况下 `clean` 就足够，`clean-all` 会删除服务定义
4. **发现 MCP 服务器**：使用 `test-mcps` 可以快速查看已安装的 MCP 服务器，然后根据 README 手动测试特定服务器
5. **日志行数根据需要调整**：启动问题用 50-100 行，运行时问题用 200-500 行
6. **组合命令**：可以用 `&&` 串联多个命令，如 `restart && logs-f`
7. **使用 root 或 sudo**：大部分命令需要 root 权限，可以直接用 root 用户或有 sudo 权限的用户执行

---

## 故障排除速查表

| 问题 | 命令 | 说明 |
| ---- | ---- | ---- |
| 不确定状态 | `./scripts/test_env.sh health` | 全面检查 |
| 服务无响应 | `./scripts/test_env.sh status` | 查看详细状态 |
| 启动失败 | `./scripts/test_env.sh logs 200` | 查看启动日志 |
| 查看 MCP 服务器 | `./scripts/test_env.sh test-mcps` | 发现已安装的 MCP |
| 配置混乱 | `./scripts/test_env.sh clean` | 清理状态 |
| 完全重置 | `./scripts/test_env.sh clean-all` | 完全清理 |
| 权限问题 | `sudo ls -la /var/lib/witty-mcp-manager` | 检查权限 |
| MCP 路径问题 | `ls -la /opt/mcp-servers/servers` | 检查 MCP 安装 |
| 服务用户问题 | `id witty-mcp` | 检查用户是否存在 |
