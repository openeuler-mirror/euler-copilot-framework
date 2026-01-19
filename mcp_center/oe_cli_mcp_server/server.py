# server.py

from config.private.mcp_server.config_loader import McpServerConfig
from oe_cli_mcp_server.loader.mcp_server import McpServer

config = McpServerConfig().get_config().private_config



if __name__ == "__main__":
    server = McpServer("mcp实例", host="0.0.0.0", port=config.port)
    server.start()
