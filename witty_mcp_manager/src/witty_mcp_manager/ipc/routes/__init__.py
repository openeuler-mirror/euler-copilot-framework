"""
IPC 路由模块

将 API 路由拆分到不同模块以降低复杂度。
"""

from witty_mcp_manager.ipc.routes.health import router as health_router
from witty_mcp_manager.ipc.routes.registry import router as registry_router
from witty_mcp_manager.ipc.routes.runtime import router as runtime_router
from witty_mcp_manager.ipc.routes.tools import router as tools_router

__all__ = [
    "health_router",
    "registry_router",
    "runtime_router",
    "tools_router",
]
