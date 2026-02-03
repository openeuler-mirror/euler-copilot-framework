"""
IPC 模块

提供 UDS HTTP/JSON API 接口，供 Witty 智能助手后端调用。
"""

from witty_mcp_manager.ipc.auth import (
    HEADER_REQUEST_ID,
    HEADER_SESSION_ID,
    HEADER_USER_ID,
    SYSTEM_USER_ID,
    UserContext,
    create_system_context,
    get_user_context,
)
from witty_mcp_manager.ipc.server import IPCServer, create_app

__all__ = [
    "HEADER_REQUEST_ID",
    "HEADER_SESSION_ID",
    "HEADER_USER_ID",
    "SYSTEM_USER_ID",
    "IPCServer",
    "UserContext",
    "create_app",
    "create_system_context",
    "get_user_context",
]
