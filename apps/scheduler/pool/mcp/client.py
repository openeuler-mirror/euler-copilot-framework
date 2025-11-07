# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Client"""

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

from apps.constants import MCP_PATH
from apps.schemas.mcp import (
    MCPServerSSEConfig,
    MCPServerStdioConfig,
    MCPStatus,
)

if TYPE_CHECKING:
    from mcp.types import CallToolResult

logger = logging.getLogger(__name__)


class MCPClient:
    """MCP客户端基类"""

    mcp_id: str
    task: asyncio.Task
    ready_sign: asyncio.Event
    error_sign: asyncio.Event
    stop_sign: asyncio.Event
    client: ClientSession
    status: MCPStatus

    def __init__(self) -> None:
        """初始化MCP Client"""
        self.status = MCPStatus.UNINITIALIZED

    async def _main_loop(
        self, user_id: str | None, mcp_id: str, config: MCPServerSSEConfig | MCPServerStdioConfig,
    ) -> None:
        """
        创建MCP Client

        抽象函数；作用为在初始化的时候使用MCP SDK创建Client
        由于目前MCP的实现中Client和Session是1:1的关系，所以直接创建了 :class:`~mcp.ClientSession`

        :param str user_id: 用户ID
        :param str mcp_id: MCP ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :return: MCP ClientSession
        :rtype: ClientSession
        """
        # 创建Client
        if isinstance(config, MCPServerSSEConfig):
            env = config.env or {}
            client = sse_client(
                url=config.url,
                headers=env,
            )
        elif isinstance(config, MCPServerStdioConfig):
            if user_id:
                cwd = MCP_PATH / "users" / user_id / mcp_id / "project"
            else:
                cwd = MCP_PATH / "template" / mcp_id / "project"
            await cwd.mkdir(parents=True, exist_ok=True)

            client = stdio_client(server=StdioServerParameters(
                command=config.command,
                args=config.args,
                env=config.env,
                cwd=cwd.as_posix(),
            ))
        else:
            self.error_sign.set()
            err = f"[MCPClient] MCP {mcp_id}：未知的MCP服务类型“{config.type}”"
            logger.error(err)
            raise TypeError(err)

        # 创建Client、Session
        try:
            exit_stack = AsyncExitStack()
            read, write = await exit_stack.enter_async_context(client)
            self.client = ClientSession(read, write)
            session = await exit_stack.enter_async_context(self.client)
            # 初始化Client
            await session.initialize()
        except Exception:
            self.error_sign.set()
            self.status = MCPStatus.STOPPED
            logger.exception("[MCPClient] MCP %s：初始化失败", mcp_id)
            raise

        self.ready_sign.set()
        self.status = MCPStatus.RUNNING

        # 等待关闭信号
        await self.stop_sign.wait()
        logger.info("[MCPClient] MCP %s：收到停止信号，正在关闭", mcp_id)

        # 关闭Client
        try:
            await exit_stack.aclose() # type: ignore[attr-defined]
            self.status = MCPStatus.STOPPED
        except Exception:
            logger.exception("[MCPClient] MCP %s：关闭失败", mcp_id)


    async def init(self, user_id: str | None, mcp_id: str, config: MCPServerSSEConfig | MCPServerStdioConfig) -> None:
        """
        初始化 MCP Client类

        初始化MCP Client，并创建MCP Server进程和ClientSession

        :param str user_id: 用户ID
        :param str mcp_id: MCP ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :return: None
        """
        # 初始化变量
        self.mcp_id = mcp_id
        self.ready_sign = asyncio.Event()
        self.error_sign = asyncio.Event()
        self.stop_sign = asyncio.Event()

        # 创建协程
        self.task = asyncio.create_task(self._main_loop(user_id, mcp_id, config))

        # 等待初始化完成
        done, pending = await asyncio.wait(
            [asyncio.create_task(self.ready_sign.wait()),
             asyncio.create_task(self.error_sign.wait())],
            return_when=asyncio.FIRST_COMPLETED,
        )
        # 取消未完成的任务
        for task in pending:
            task.cancel()

        if self.error_sign.is_set():
            self.status = MCPStatus.ERROR
            err_msg = f"[MCPClient] MCP {mcp_id} 初始化失败"
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        # 获取工具列表
        self.tools = (await self.client.list_tools()).tools


    async def call_tool(self, tool_name: str, params: dict) -> "CallToolResult":
        """调用MCP Server的工具"""
        return await self.client.call_tool(tool_name, params)


    async def stop(self) -> None:
        """停止MCP Client"""
        self.stop_sign.set()
        try:
            await self.task
        except Exception as e:  # noqa: BLE001
            logger.warning("[MCPClient] MCP %s：停止时发生异常：%s", self.mcp_id, e)
