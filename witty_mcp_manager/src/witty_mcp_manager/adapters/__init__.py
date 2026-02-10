"""
Witty MCP Manager - Adapters 模块

提供不同传输协议的适配器实现，支持 STDIO、SSE、HTTP 三种传输方式。
"""

from witty_mcp_manager.adapters.base import (
    AdapterType,
    BaseAdapter,
    Tool,
    ToolCallResult,
    ToolsCache,
    clear_global_cache,
    get_cache_lock,
    get_global_cached_tools,
    update_global_cached_tools,
)
from witty_mcp_manager.adapters.http import StreamableHTTPAdapter
from witty_mcp_manager.adapters.sse import SSEAdapter
from witty_mcp_manager.adapters.stdio import STDIOAdapter

__all__ = [
    "AdapterType",
    "BaseAdapter",
    "SSEAdapter",
    "STDIOAdapter",
    "StreamableHTTPAdapter",
    "Tool",
    "ToolCallResult",
    "ToolsCache",
    "clear_global_cache",
    "get_cache_lock",
    "get_global_cached_tools",
    "update_global_cached_tools",
]
