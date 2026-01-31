"""
适配器基类模块

定义所有传输适配器的统一接口。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    import types

    from witty_mcp_manager.overlay.resolver import EffectiveConfig
    from witty_mcp_manager.registry.models import ServerRecord
    from witty_mcp_manager.runtime.manager import Session

logger = logging.getLogger(__name__)


class AdapterType(str, Enum):
    """适配器类型"""

    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable_http"


@dataclass
class Tool:
    """
    MCP Tool 定义

    对应 MCP 协议中的 Tool schema
    """

    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }

    @classmethod
    def from_mcp_tool(cls, mcp_tool: Any) -> Tool:
        """从 MCP SDK Tool 对象创建"""
        return cls(
            name=mcp_tool.name,
            description=mcp_tool.description or "",
            input_schema=mcp_tool.inputSchema if hasattr(mcp_tool, "inputSchema") else {},
        )


@dataclass
class ToolCallResult:
    """
    Tool 调用结果

    对应 MCP 协议中的 CallToolResult
    """

    success: bool
    content: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    is_error: bool = False
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        result: dict[str, Any] = {
            "success": self.success,
            "content": self.content,
        }
        if self.error:
            result["error"] = self.error
        if self.is_error:
            result["isError"] = self.is_error
        return result

    @classmethod
    def from_mcp_result(cls, mcp_result: Any, duration_ms: int = 0) -> ToolCallResult:
        """从 MCP SDK CallToolResult 创建"""
        content = []
        if hasattr(mcp_result, "content"):
            for item in mcp_result.content:
                if hasattr(item, "text"):
                    content.append({"type": "text", "text": item.text})
                elif hasattr(item, "data"):
                    content.append({"type": "image", "data": item.data, "mimeType": item.mimeType})
                else:
                    content.append({"type": "unknown", "data": str(item)})

        is_error = getattr(mcp_result, "isError", False)
        return cls(
            success=not is_error,
            content=content,
            is_error=is_error,
            duration_ms=duration_ms,
        )

    @classmethod
    def error_result(cls, error: str, duration_ms: int = 0) -> ToolCallResult:
        """创建错误结果"""
        return cls(
            success=False,
            content=[{"type": "text", "text": error}],
            error=error,
            is_error=True,
            duration_ms=duration_ms,
        )


@dataclass
class ToolsCache:
    """
    Tools 缓存

    缓存已发现的 Tools，避免频繁请求
    """

    tools: list[Tool]
    cached_at: datetime
    ttl_seconds: int = 600  # 默认 10 分钟

    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        elapsed = (datetime.now(UTC) - self.cached_at).total_seconds()
        return elapsed >= self.ttl_seconds


class BaseAdapter(ABC):
    """
    适配器基类

    定义所有传输适配器必须实现的接口
    """

    adapter_type: AdapterType

    def __init__(self, server: ServerRecord, config: EffectiveConfig) -> None:
        """
        初始化适配器

        Args:
            server: MCP Server 记录
            config: 最终生效配置

        """
        self.server = server
        self.config = config
        self._tools_cache: ToolsCache | None = None
        self._connected = False

    @property
    def mcp_id(self) -> str:
        """获取 MCP ID"""
        return self.server.id

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected

    @abstractmethod
    async def connect(self, session: Session) -> None:
        """
        建立连接

        Args:
            session: 会话实例

        Raises:
            AdapterError: 连接失败

        """

    @abstractmethod
    async def disconnect(self) -> None:
        """
        断开连接

        Raises:
            AdapterError: 断开失败

        """

    @abstractmethod
    async def discover_tools(self, *, force_refresh: bool = False) -> list[Tool]:
        """
        发现可用的 Tools

        Args:
            force_refresh: 是否强制刷新（忽略缓存）

        Returns:
            Tool 列表

        Raises:
            AdapterError: 发现失败

        """

    @abstractmethod
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout_ms: int | None = None,
    ) -> ToolCallResult:
        """
        调用 Tool

        Args:
            tool_name: Tool 名称
            arguments: 调用参数
            timeout_ms: 超时时间（毫秒）

        Returns:
            调用结果

        Raises:
            AdapterError: 调用失败
            ToolCallError: Tool 执行错误

        """

    def _get_cached_tools(self) -> list[Tool] | None:
        """获取缓存的 Tools（如未过期）"""
        if self._tools_cache and not self._tools_cache.is_expired:
            return self._tools_cache.tools
        return None

    def _set_cached_tools(self, tools: list[Tool]) -> None:
        """设置 Tools 缓存"""
        ttl = self.config.config.tool_policy.cache_ttl if self.config else 600
        self._tools_cache = ToolsCache(
            tools=tools,
            cached_at=datetime.now(UTC),
            ttl_seconds=ttl,
        )

    def _clear_cache(self) -> None:
        """清除缓存"""
        self._tools_cache = None

    async def __aenter__(self) -> Self:
        """异步上下文管理器入口"""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """异步上下文管理器退出"""
        await self.disconnect()
