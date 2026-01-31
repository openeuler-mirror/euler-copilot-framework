"""
Witty MCP Manager - Overlay 模块

提供覆盖配置的持久化存储和解析能力，支持全局和用户级配置覆盖。
"""

from witty_mcp_manager.overlay.resolver import OverlayResolver
from witty_mcp_manager.overlay.storage import OverlayStorage

__all__ = [
    "OverlayStorage",
    "OverlayResolver",
]
