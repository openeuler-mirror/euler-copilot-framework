#!/bin/bash
set -e


# 3. 部署systemd服务
cp /usr/lib/sysagent/mcp_center/service/oe-mcp.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable oe-mcp --now
systemctl start oe-mcp
echo "✅ 服务已启动"
# 4. 全局命令链接

chmod +x /usr/lib/sysagent/mcp_center/oe_cli_mcp_server/cli/cli.py
rm -f /usr/local/bin/oe-mcp
ln -s /usr/lib/sysagent/mcp_center/oe_cli_mcp_server/cli/cli.py /usr/local/bin/oe-mcp