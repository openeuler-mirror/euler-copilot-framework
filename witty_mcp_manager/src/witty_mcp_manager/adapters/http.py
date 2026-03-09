"""
Streamable HTTP 适配器模块

通过 HTTP+SSE 与远程 MCP Server 通信。

注意: 这是为 MCP 新版本 Streamable HTTP 协议预留的适配器。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from witty_mcp_manager.adapters.base import (
    AdapterType,
    BaseAdapter,
    Tool,
    ToolCallResult,
)
from witty_mcp_manager.exceptions import AdapterError

if TYPE_CHECKING:
    from witty_mcp_manager.overlay.resolver import EffectiveConfig
    from witty_mcp_manager.registry.models import ServerRecord
    from witty_mcp_manager.runtime.manager import Session

logger = logging.getLogger(__name__)


class StreamableHTTPAdapter(BaseAdapter):
    """
    Streamable HTTP 适配器

    为 MCP 新版本协议预留，暂未实现
    """

    adapter_type = AdapterType.STREAMABLE_HTTP

    def __init__(self, server: ServerRecord, config: EffectiveConfig) -> None:
        """
        初始化 HTTP 适配器

        Args:
            server: MCP Server 记录
            config: 最终生效配置

        """
        super().__init__(server, config)
        logger.warning("StreamableHTTPAdapter is a placeholder for future MCP protocol - not yet implemented")

    async def connect(self, session: Session) -> None:
        """
        建立连接

        Raises:
            AdapterError: 协议未实现

        """
        msg = "StreamableHTTPAdapter is not implemented - waiting for MCP protocol specification"
        raise AdapterError(msg, adapter_type="streamable_http")

    async def disconnect(self) -> None:
        """断开连接"""
        if not self._connected:
            return
        self._connected = False

    async def discover_tools(self, *, force_refresh: bool = False) -> list[Tool]:
        """
        发现可用的 Tools

        Raises:
            AdapterError: 协议未实现

        """
        msg = "StreamableHTTPAdapter is not implemented - waiting for MCP protocol specification"
        raise AdapterError(msg, adapter_type="streamable_http")

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout_ms: int | None = None,
    ) -> ToolCallResult:
        """
        调用 Tool

        Raises:
            AdapterError: 协议未实现

        """
        msg = "StreamableHTTPAdapter is not implemented - waiting for MCP protocol specification"
        raise AdapterError(msg, adapter_type="streamable_http")
