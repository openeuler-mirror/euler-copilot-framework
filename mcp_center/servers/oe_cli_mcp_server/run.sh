#!/bin/bash

# 关键路径（只改这里就行）
VENV_PATH="/usr/lib/euler-copilot-framework/mcp_center/servers/oe_cli_mcp_server/venv/global"
REQUIREMENTS="/usr/lib/euler-copilot-framework/mcp_center/servers/oe_cli_mcp_server/requirements.txt"

# 1. 没有虚拟环境就创建
if [ ! -d "$VENV_PATH" ]; then
  python3 -m venv "$VENV_PATH"
fi

# 2. 激活虚拟环境 + 升级pip + 装依赖
source "$VENV_PATH/bin/activate"
pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -r "$REQUIREMENTS" -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 部署systemd服务
cp /usr/lib/euler-copilot-framework/mcp_center/servers/oe_cli_mcp_server/mcp-server.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable mcp-server --now


# 4. 全局命令链接
chmod +x /usr/lib/euler-copilot-framework/mcp_center/servers/oe_cli_mcp_server/mcp_server/cli.py
rm -f /usr/local/bin/mcp-server
ln -s /usr/lib/euler-copilot-framework/mcp_center/servers/oe_cli_mcp_server/mcp_server/cli.py /usr/local/bin/mcp-server
