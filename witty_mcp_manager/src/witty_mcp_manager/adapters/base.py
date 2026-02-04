"""
适配器基类模块

定义所有传输适配器的统一接口。
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Self

from witty_mcp_manager.security.redaction import get_redactor

if TYPE_CHECKING:
    import types

    from witty_mcp_manager.overlay.resolver import EffectiveConfig
    from witty_mcp_manager.registry.models import ServerRecord
    from witty_mcp_manager.runtime.manager import Session

logger = logging.getLogger(__name__)

# 全局工具缓存：按 mcp_id 存储 (tools, cached_at, lock)
GLOBAL_TOOLS_CACHE: dict[str, tuple[list[Tool], datetime, asyncio.Lock]] = {}


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
        self._connected = False

    @property
    def mcp_id(self) -> str:
        """获取 MCP ID"""
        return self.server.id

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected

    def get_cache_ttl(self) -> int:
        """获取缓存 TTL 配置"""
        return self.config.config.tool_policy.cache_ttl if self.config else 600

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

    def _redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """脱敏日志数据"""
        return get_redactor().redact_dict(data)

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


def _get_or_create_cache_entry(mcp_id: str) -> tuple[list[Tool], datetime, asyncio.Lock]:
    """
    获取或创建全局缓存条目

    Args:
        mcp_id: MCP Server ID

    Returns:
        (tools, cached_at, lock) 元组

    """
    if mcp_id not in GLOBAL_TOOLS_CACHE:
        GLOBAL_TOOLS_CACHE[mcp_id] = ([], datetime.min.replace(tzinfo=UTC), asyncio.Lock())
    return GLOBAL_TOOLS_CACHE[mcp_id]


async def get_global_cached_tools(
    mcp_id: str,
    ttl_seconds: int,
    *,
    force_refresh: bool = False,
) -> list[Tool] | None:
    """
    从全局缓存获取工具列表

    Args:
        mcp_id: MCP Server ID
        ttl_seconds: 缓存过期时间（秒）
        force_refresh: 是否强制刷新

    Returns:
        如果缓存有效返回工具列表，否则返回 None

    """
    if force_refresh:
        return None

    tools, cached_at, _ = _get_or_create_cache_entry(mcp_id)

    if not tools:
        return None

    # 检查是否过期
    elapsed = (datetime.now(UTC) - cached_at).total_seconds()
    if elapsed >= ttl_seconds:
        return None

    # 返回防御性拷贝
    return tools.copy()


async def update_global_cached_tools(
    mcp_id: str,
    tools: list[Tool],
) -> None:
    """
    更新全局缓存

    Args:
        mcp_id: MCP Server ID
        tools: 工具列表

    """
    _, _, lock = _get_or_create_cache_entry(mcp_id)
    GLOBAL_TOOLS_CACHE[mcp_id] = (tools, datetime.now(UTC), lock)


async def get_cache_lock(mcp_id: str) -> asyncio.Lock:
    """
    获取指定 MCP Server 的缓存锁

    Args:
        mcp_id: MCP Server ID

    Returns:
        异步锁

    """
    _, _, lock = _get_or_create_cache_entry(mcp_id)
    return lock


def clear_global_cache(mcp_id: str | None = None) -> None:
    """
    清除全局缓存

    Args:
        mcp_id: MCP Server ID，如果为 None 则清除所有缓存

    """
    if mcp_id is None:
        GLOBAL_TOOLS_CACHE.clear()
    elif mcp_id in GLOBAL_TOOLS_CACHE:
        del GLOBAL_TOOLS_CACHE[mcp_id]
