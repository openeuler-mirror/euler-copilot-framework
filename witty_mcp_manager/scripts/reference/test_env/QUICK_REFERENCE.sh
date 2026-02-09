#!/usr/bin/env bash
# 测试环境快速参考 - 放在终端边上的小抄
# 所有命令都在 witty_mcp_manager/ 目录下执行

# ============================================
# 🚀 首次设置（推荐开发模式）
# ============================================
./scripts/test_env.sh setup-dev        # 1️⃣ 配置开发环境
./scripts/test_env.sh install-dev      # 2️⃣ 安装开发服务
DEV_MODE=true ./scripts/test_env.sh start  # 3️⃣ 启动开发服务

# 或者生产模式（需要先构建二进制）
./scripts/build_nuitka.sh              # 1️⃣ 构建二进制
sudo cp dist/witty-mcp /usr/bin/witty-mcp  # 2️⃣ 安装二进制
sudo chmod 755 /usr/bin/witty-mcp
./scripts/test_env.sh install          # 3️⃣ 安装生产服务
./scripts/test_env.sh start            # 4️⃣ 启动生产服务

# 💡 简化开发模式命令
alias wmm-dev='DEV_MODE=true ./scripts/test_env.sh'
# 然后使用: wmm-dev start, wmm-dev status, etc.

# ============================================
# 📊 日常命令（开发模式）
# ============================================
DEV_MODE=true ./scripts/test_env.sh status       # 查看服务状态
DEV_MODE=true ./scripts/test_env.sh logs         # 查看日志（最近100行）
DEV_MODE=true ./scripts/test_env.sh logs-f       # 实时跟随日志 ⭐
DEV_MODE=true ./scripts/test_env.sh restart      # 重启服务
DEV_MODE=true ./scripts/test_env.sh health       # 健康检查

# ============================================
# 📊 日常命令（生产模式）
# ============================================
./scripts/test_env.sh status           # 查看服务状态
./scripts/test_env.sh logs             # 查看日志（最近100行）
./scripts/test_env.sh logs-f           # 实时跟随日志 ⭐
./scripts/test_env.sh restart          # 重启服务
./scripts/test_env.sh health           # 健康检查

# ============================================
# 🧪 MCP 测试
# ============================================
./scripts/test_env.sh test-mcps                 # 列出所有 MCP 服务器
./scripts/test_env.sh test-mcps ping-all        # mcp-cli 逐个 ping 所有 ⭐
./scripts/test_env.sh test-mcps ping git_mcp    # ping 单个服务器
./scripts/test_env.sh test-mcps tools cvekit_mcp  # 查看工具列表 (JSON)
./scripts/test_env.sh test-mcps call git_mcp git_status '{"repo_path":"/tmp"}'  # 调用工具
./scripts/test_env.sh test-mcps help            # 子命令帮助

# ============================================
# 🧹 清理操作
# ============================================
./scripts/test_env.sh clean        # 清理状态（保留服务）
./scripts/test_env.sh clean-all    # 完全清理（需重新部署）

# ============================================
# 🔧 自定义配置
# ============================================
DEV_MODE=true MCP_SERVERS_PATH=/custom/path ./scripts/test_env.sh test-mcps
DEV_MODE=true STATE_DIR=/var/lib/custom-witty ./scripts/test_env.sh status
DEV_MODE=true WITTY_USER=my-user ./scripts/test_env.sh test-mcps

# ============================================
# 🐛 问题排查流程
# ============================================
./scripts/test_env.sh health       # 1️⃣ 健康检查
./scripts/test_env.sh logs 200     # 2️⃣ 查看详细日志
./scripts/test_env.sh restart      # 3️⃣ 尝试重启
./scripts/test_env.sh test-mcps    # 4️⃣ 检查 MCP 服务器
./scripts/test_env.sh test-mcps ping-all  # 5️⃣ ping 所有 MCP

# ============================================
# 📚 详细文档
# ============================================
./scripts/test_env.sh help         # 查看完整帮助
cat scripts/reference/test_env/TEST_ENV_GUIDE.md     # 详细使用指南

# ============================================
# ⚡ 开发调试循环（开发模式）
# ============================================
# 1. 本地修改代码
# 2. 运行测试: uv run pytest -v
# 3. 重启服务: DEV_MODE=true ./scripts/test_env.sh restart
# 4. 查看日志: DEV_MODE=true ./scripts/test_env.sh logs-f

# ============================================
# 💡 提示
# ============================================
# - 开发模式需要 DEV_MODE=true 或设置别名
# - 开发模式使用 uv run，代码修改后重启即生效
# - 生产模式需要先 pip install 或 RPM 安装
# - 两种模式可以同时安装运行（不同服务名）
# - logs-f 可以实时查看启动过程
# - health 可以快速诊断环境问题
# - test-mcps 优先通过 daemon UDS socket 查询
# - test-mcps ping 需要 mcp-cli (uv tool install mcp-cli; 安装后如不在 PATH 中，请运行 uv tool update-shell)
# - test-mcps call 可直接调用 MCP 工具并显示 JSON 结果
# - clean 不会删除服务，可放心使用
# - 大部分命令需要 root 或 sudo 权限
