cp mcp-server.service /etc/systemd/system/

source venv/global/bin/activate


systemctl daemon-reload
systemctl enable mcp-server.service
systemctl start mcp-server.service
systemctl status mcp-server

chmod +x /home/tsn/oe-cli-mcp-server/mcp_server/cli.py
rm -f /usr/local/bin/mcp-server
sudo ln -s /home/tsn/oe-cli-mcp-server/mcp_server/cli.py /usr/local/bin/mcp-server