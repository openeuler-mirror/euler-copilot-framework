cp mcp-server.service /etc/systemd/system/

source venv/global/bin/activate

pip install --upgrade pip
pip install -r /usr/lib/euler-copilot-framework/mcp_center/servers/oe-cli-mcp-server/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

systemctl daemon-reload
systemctl enable mcp-server.service
systemctl start mcp-server.service
systemctl status mcp-server

chmod +x /usr/lib/euler-copilot-framework/mcp_center/servers/oe-cli-mcp-server/mcp_server/cli.py
rm -f /usr/local/bin/mcp-server
sudo ln -s /usr/lib/euler-copilot-framework/mcp_center/servers/oe-cli-mcp-server/mcp_server/cli.py /usr/local/bin/mcp-server