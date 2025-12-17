# server.py
import sys
from pathlib import Path
mcp_center_dir = Path(__file__).parent.parent.parent  # 关键：根据目录层级调整
sys.path.append(str(mcp_center_dir))
from config.private.mcp_server.config_loader import McpServerConfig
from servers.oe_cli_mcp_server.mcp_server.mcp_manager import McpServer

config = McpServerConfig().get_config().private_config



if __name__ == "__main__":
    server = McpServer("mcp实例", host="0.0.0.0", port=config.port)
    server.start()
