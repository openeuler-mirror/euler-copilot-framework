# server.py
import os
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from config.base_config_loader import BaseConfig
from mcp_server.mcp_manager import McpServer

config = BaseConfig().get_config().public_config



if __name__ == "__main__":
    server = McpServer("mcp实例", host=config.host, port=config.port)
    server.start()
