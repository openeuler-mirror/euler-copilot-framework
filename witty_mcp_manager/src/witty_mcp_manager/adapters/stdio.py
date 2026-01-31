"""
STDIO 适配器模块

通过子进程 + stdin/stdout 与 MCP Server 通信。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from witty_mcp_manager.adapters.base import (
    AdapterType,
    BaseAdapter,
    Tool,
    ToolCallResult,
)
from witty_mcp_manager.exceptions import AdapterError, ToolCallError

if TYPE_CHECKING:
    from witty_mcp_manager.overlay.resolver import EffectiveConfig
    from witty_mcp_manager.registry.models import ServerRecord
    from witty_mcp_manager.runtime.manager import Session

logger = logging.getLogger(__name__)


class STDIOAdapter(BaseAdapter):
    """
    STDIO 适配器

    通过 stdio_client 启动子进程并通过 stdin/stdout 通信
    """

    adapter_type = AdapterType.STDIO

    def __init__(self, server: ServerRecord, config: EffectiveConfig) -> None:
        """
        初始化 STDIO 适配器

        Args:
            server: MCP Server 记录
            config: 最终生效配置

        """
        super().__init__(server, config)
        self._session: ClientSession | None = None
        self._client_context: Any = None
        self._session_context: Any = None

    def _build_server_params(self) -> StdioServerParameters:
        """
        构建 STDIO Server 参数

        Returns:
            StdioServerParameters 实例

        """
        stdio_config = self.config.config.stdio
        if not stdio_config:
            msg = f"STDIO config not found for {self.mcp_id}"
            raise AdapterError(msg, adapter_type="stdio")

        # 合并环境变量（配置 env + overlay env）
        env: dict[str, str] = {}
        if stdio_config.env:
            env.update(stdio_config.env)
        if self.config.env:
            env.update(self.config.env)

        return StdioServerParameters(
            command=stdio_config.command,
            args=stdio_config.args,
            env=env if env else None,
            cwd=stdio_config.cwd,
        )

    async def connect(self, session: Session) -> None:
        """
        建立连接（启动子进程）

        Args:
            session: 会话实例

        Raises:
            AdapterError: 连接失败

        """
        if self._connected:
            logger.debug("Already connected to %s", self.mcp_id)
            return

        try:
            params = self._build_server_params()
            logger.info(
                "Starting STDIO MCP: %s (command=%s, args=%s)",
                self.mcp_id,
                params.command,
                params.args,
            )

            # 创建 stdio client 上下文
            self._client_context = stdio_client(params)
            read_stream, write_stream = await self._client_context.__aenter__()

            # 创建 session 上下文
            self._session_context = ClientSession(read_stream, write_stream)
            self._session = await self._session_context.__aenter__()

            # 初始化会话
            await self._session.initialize()

            self._connected = True
            logger.info("Connected to STDIO MCP: %s", self.mcp_id)

            # 更新 session 状态
            await session.mark_running()

        except Exception as e:
            logger.exception("Failed to connect to STDIO MCP %s: %s", self.mcp_id, e)
            await self._cleanup()
            msg = f"Failed to connect to {self.mcp_id}: {e}"
            raise AdapterError(msg, adapter_type="stdio") from e

    async def disconnect(self) -> None:
        """
        断开连接（终止子进程）

        Raises:
            AdapterError: 断开失败

        """
        if not self._connected:
            return

        logger.info("Disconnecting from STDIO MCP: %s", self.mcp_id)
        await self._cleanup()
        logger.info("Disconnected from STDIO MCP: %s", self.mcp_id)

    async def _cleanup(self) -> None:
        """清理资源"""
        try:
            if self._session_context:
                await self._session_context.__aexit__(None, None, None)
        except Exception as e:
            logger.warning("Error closing session: %s", e)
        finally:
            self._session = None
            self._session_context = None

        try:
            if self._client_context:
                await self._client_context.__aexit__(None, None, None)
        except Exception as e:
            logger.warning("Error closing client: %s", e)
        finally:
            self._client_context = None

        self._connected = False
        self._clear_cache()

    async def discover_tools(self, force_refresh: bool = False) -> list[Tool]:
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
            raise AdapterError(msg, adapter_type="stdio")

        # 检查缓存
        if not force_refresh:
            cached = self._get_cached_tools()
            if cached is not None:
                logger.debug("Using cached tools for %s (%d tools)", self.mcp_id, len(cached))
                return cached

        try:
            logger.debug("Discovering tools for %s", self.mcp_id)
            result = await self._session.list_tools()

            tools = [Tool.from_mcp_tool(t) for t in result.tools]
            self._set_cached_tools(tools)

            logger.info("Discovered %d tools for %s", len(tools), self.mcp_id)
            return tools

        except Exception as e:
            logger.exception("Failed to discover tools for %s: %s", self.mcp_id, e)
            msg = f"Failed to discover tools for {self.mcp_id}: {e}"
            raise AdapterError(msg, adapter_type="stdio") from e

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
            raise AdapterError(msg, adapter_type="stdio")

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

            logger.info(
                "Tool %s on %s completed in %dms (success=%s)",
                tool_name,
                self.mcp_id,
                duration_ms,
                tool_result.success,
            )

            return tool_result

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
                "Tool %s on %s failed: %s",
                tool_name,
                self.mcp_id,
                e,
            )
            msg = f"Tool call failed: {e}"
            raise ToolCallError(msg, tool_name=tool_name, mcp_id=self.mcp_id) from e
