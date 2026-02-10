"""
SSE 适配器模块

通过 Server-Sent Events 与远程 MCP Server 通信。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from mcp import ClientSession
from mcp.client.sse import sse_client

from witty_mcp_manager.adapters.base import (
    AdapterType,
    BaseAdapter,
    Tool,
    ToolCallResult,
    get_cache_lock,
    get_global_cached_tools,
    update_global_cached_tools,
)
from witty_mcp_manager.exceptions import AdapterError, ToolCallError

if TYPE_CHECKING:
    from witty_mcp_manager.overlay.resolver import EffectiveConfig
    from witty_mcp_manager.registry.models import ServerRecord
    from witty_mcp_manager.runtime.manager import Session

logger = logging.getLogger(__name__)


class SSEAdapter(BaseAdapter):
    """
    SSE 适配器

    通过 sse_client 连接远程 SSE 服务
    """

    adapter_type = AdapterType.SSE

    def __init__(self, server: ServerRecord, config: EffectiveConfig) -> None:
        """
        初始化 SSE 适配器

        Args:
            server: MCP Server 记录
            config: 最终生效配置

        """
        super().__init__(server, config)
        self._session: ClientSession | None = None
        self._client_context: Any = None
        self._session_context: Any = None

    def _get_sse_url(self) -> str:
        """
        获取 SSE URL

        Returns:
            SSE 服务 URL

        """
        sse_config = self.config.config.sse
        if not sse_config:
            msg = f"SSE config not found for {self.mcp_id}"
            raise AdapterError(msg, adapter_type="sse")
        return sse_config.url

    def _get_headers(self) -> dict[str, str]:
        """
        获取请求头

        Returns:
            请求头字典

        """
        headers: dict[str, str] = {}

        # 从 SSE config 获取
        sse_config = self.config.config.sse
        if sse_config and sse_config.headers:
            headers.update(sse_config.headers)

        # 从 overlay 获取（优先级更高）
        if self.config.headers:
            headers.update(self.config.headers)

        return headers

    async def connect(self, session: Session) -> None:
        """
        建立 SSE 连接

        Args:
            session: 会话实例

        Raises:
            AdapterError: 连接失败

        """
        if self._connected:
            logger.debug("Already connected to %s", self.mcp_id)
            return

        url = self._get_sse_url()
        headers = self._get_headers()

        try:
            logger.info("Connecting to SSE MCP: %s (url=%s)", self.mcp_id, url)

            # 创建 SSE client 上下文
            self._client_context = sse_client(url=url, headers=headers if headers else None)
            read_stream, write_stream = await self._client_context.__aenter__()

            # 创建 session 上下文
            self._session_context = ClientSession(read_stream, write_stream)
            self._session = await self._session_context.__aenter__()

            # 初始化会话
            await self._session.initialize()

            self._connected = True
            logger.info("Connected to SSE MCP: %s", self.mcp_id)

            # 更新 session 状态
            await session.mark_running()

        except Exception as e:
            logger.exception("Failed to connect to SSE MCP %s", self.mcp_id)
            await self._cleanup()
            msg = f"Failed to connect to {self.mcp_id}: {e}"
            raise AdapterError(msg, adapter_type="sse") from e

    async def disconnect(self) -> None:
        """
        断开 SSE 连接

        Raises:
            AdapterError: 断开失败

        """
        if not self._connected:
            return

        logger.info("Disconnecting from SSE MCP: %s", self.mcp_id)
        await self._cleanup()
        logger.info("Disconnected from SSE MCP: %s", self.mcp_id)

    async def _cleanup(self) -> None:
        """清理资源"""
        try:
            if self._session_context:
                await self._session_context.__aexit__(None, None, None)
        except OSError as e:
            logger.warning("Error closing session: %s", e)
        finally:
            self._session = None
            self._session_context = None

        try:
            if self._client_context:
                await self._client_context.__aexit__(None, None, None)
        except OSError as e:
            logger.warning("Error closing client: %s", e)
        finally:
            self._client_context = None

        self._connected = False

    async def discover_tools(self, *, force_refresh: bool = False) -> list[Tool]:
        """
        发现可用的 Tools

        Args:
            force_refresh: 是否强制刷新

        Returns:
            Tool 列表

        Raises:
            AdapterError: 发现失败

        """
        if not self._connected or not self._session:
            msg = f"Not connected to {self.mcp_id}"
            raise AdapterError(msg, adapter_type="sse")

        # 尝试从全局缓存获取
        ttl = self.get_cache_ttl()
        cached = await get_global_cached_tools(self.mcp_id, ttl, force_refresh=force_refresh)
        if cached is not None:
            logger.debug("Using cached tools for %s (%d tools)", self.mcp_id, len(cached))
            return cached

        # 获取锁，避免并发重复请求
        lock = await get_cache_lock(self.mcp_id)
        async with lock:
            # 双重检查：可能其他协程已经更新了缓存
            cached = await get_global_cached_tools(self.mcp_id, ttl, force_refresh=False)
            if cached is not None and not force_refresh:
                logger.debug("Using cached tools for %s after lock (%d tools)", self.mcp_id, len(cached))
                return cached

            try:
                logger.debug("Discovering tools for %s", self.mcp_id)
                result = await self._session.list_tools()
                tools = [Tool.from_mcp_tool(t) for t in result.tools]
                await update_global_cached_tools(self.mcp_id, tools)

            except Exception as e:
                logger.exception("Failed to discover tools for %s", self.mcp_id)
                msg = f"Failed to discover tools for {self.mcp_id}: {e}"
                raise AdapterError(msg, adapter_type="sse") from e

            else:
                logger.info("Discovered %d tools for %s", len(tools), self.mcp_id)
                return tools

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
        if not self._connected or not self._session:
            msg = f"Not connected to {self.mcp_id}"
            raise AdapterError(msg, adapter_type="sse")

        # 确定超时时间
        timeout_s = (timeout_ms / 1000) if timeout_ms else self.config.timeouts.tool_call
        start_time = time.monotonic()

        try:
            logger.debug(
                "Calling tool %s on %s with args: %s",
                tool_name,
                self.mcp_id,
                arguments,
            )

            # 使用 asyncio.wait_for 实现超时
            result = await asyncio.wait_for(
                self._session.call_tool(tool_name, arguments),
                timeout=timeout_s,
            )

            duration_ms = int((time.monotonic() - start_time) * 1000)
            tool_result = ToolCallResult.from_mcp_result(result, duration_ms)

        except TimeoutError:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.warning(
                "Tool %s on %s timed out after %dms",
                tool_name,
                self.mcp_id,
                duration_ms,
            )
            return ToolCallResult.error_result(
                f"Tool call timed out after {timeout_s}s",
                duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.exception(
                "Tool %s on %s failed",
                tool_name,
                self.mcp_id,
            )
            msg = f"Tool call failed: {e}"
            raise ToolCallError(msg, tool_name=tool_name, mcp_id=self.mcp_id) from e

        else:
            logger.info(
                "Tool %s on %s completed in %dms (success=%s)",
                tool_name,
                self.mcp_id,
                duration_ms,
                tool_result.success,
            )
            return tool_result

    async def reconnect(self, session: Session) -> None:
        """
        重新连接

        Args:
            session: 会话实例

        """
        logger.info("Reconnecting to SSE MCP: %s", self.mcp_id)
        await self.disconnect()
        await self.connect(session)
