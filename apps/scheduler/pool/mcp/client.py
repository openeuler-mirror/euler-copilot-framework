# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Client"""

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

import httpx
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
        self, user_sub: str | None, mcp_id: str, config: MCPServerSSEConfig | MCPServerStdioConfig,
    ) -> None:
        """
        创建MCP Client

        抽象函数；作用为在初始化的时候使用MCP SDK创建Client
        由于目前MCP的实现中Client和Session是1:1的关系，所以直接创建了 :class:`~mcp.ClientSession`

        :param str user_sub: 用户ID
        :param str mcp_id: MCP ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :return: MCP ClientSession
        :rtype: ClientSession
        """
        # 创建Client
        if isinstance(config, MCPServerSSEConfig):
            headers = config.headers or {}
            # 添加超时配置
            timeout = getattr(config, 'timeout', 30)  # 默认30秒超时
            logger.info("[MCPClient] MCP %s：尝试连接SSE端点 %s，超时时间: %s秒", mcp_id, config.url, timeout)
            
            try:
                # 先测试端点可达性 - 对于SSE端点，我们只检查连接性，不读取内容
                async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=3.0)) as test_client:
                    try:
                        # 首先尝试HEAD请求
                        response = await test_client.head(config.url, headers=headers)
                        logger.info("[MCPClient] MCP %s：端点预检查响应状态 %s", mcp_id, response.status_code)
                        
                        # 如果HEAD请求返回404，尝试流式GET请求验证连接性
                        if response.status_code == 404:
                            logger.info("[MCPClient] MCP %s：HEAD请求返回404，尝试流式连接验证", mcp_id)
                            try:
                                # 使用stream=True避免读取完整响应，只验证连接
                                async with test_client.stream('GET', config.url, headers=headers) as stream_response:
                                    if stream_response.status_code == 200:
                                        logger.info("[MCPClient] MCP %s：流式连接成功，端点可用", mcp_id)
                                        # 立即关闭流，不读取内容
                                    else:
                                        logger.warning("[MCPClient] MCP %s：流式连接返回状态 %s", mcp_id, stream_response.status_code)
                            except httpx.ReadTimeout:
                                # 对于SSE端点，读取超时是正常的，说明连接成功但在等待流数据
                                logger.info("[MCPClient] MCP %s：连接成功但读取超时（SSE端点正常行为）", mcp_id)
                            except Exception as get_e:
                                logger.error("[MCPClient] MCP %s：流式连接失败: %s", mcp_id, get_e)
                                raise ConnectionError(f"MCP端点不可用: {config.url}")
                        
                    except httpx.ConnectTimeout:
                        logger.error("[MCPClient] MCP %s：连接超时", mcp_id)
                        raise ConnectionError(f"无法连接到MCP端点 {config.url}: 连接超时")
                    except httpx.RequestError as e:
                        logger.error("[MCPClient] MCP %s：端点预检查失败: %s", mcp_id, e)
                        raise ConnectionError(f"无法连接到MCP端点 {config.url}: {e}")
                    except httpx.HTTPStatusError as e:
                        logger.warning("[MCPClient] MCP %s：端点返回HTTP错误 %s", mcp_id, e.response.status_code)
                        # 对于SSE端点，某些HTTP错误是可以接受的
                        
            except ConnectionError:
                # 重新抛出连接错误
                self.error_sign.set()
                self.status = MCPStatus.ERROR
                raise
            except Exception as e:
                logger.warning("[MCPClient] MCP %s：连接预检查遇到异常，但继续尝试连接: %s", mcp_id, e)
                # 对于其他异常，记录警告但不阻止连接尝试
                
            client = sse_client(
                url=config.url,
                headers=headers
            )
        elif isinstance(config, MCPServerStdioConfig):
            if user_sub:
                cwd = MCP_PATH / "users" / user_sub / mcp_id / "project"
            else:
                cwd = MCP_PATH / "template" / mcp_id / "project"
            await cwd.mkdir(parents=True, exist_ok=True)
            logger.info("[MCPClient] MCP %s：创建Stdio客户端，工作目录: %s", mcp_id, cwd.as_posix())
            client = stdio_client(server=StdioServerParameters(
                command=config.command,
                args=config.args,
                env=config.env,
                cwd=cwd.as_posix(),
            ))
        else:
            self.error_sign.set()
            err = f"[MCPClient] MCP {mcp_id}：未知的MCP服务类型'{config.type}'"
            logger.error(err)
            raise TypeError(err)

        # 创建Client、Session
        exit_stack = AsyncExitStack()
        try:
            logger.info("[MCPClient] MCP %s：开始建立连接", mcp_id)
            
            # 设置超时时间
            timeout_duration = getattr(config, 'timeout', 30)
            read, write = await asyncio.wait_for(
                exit_stack.enter_async_context(client),
                timeout=timeout_duration
            )
            
            self.client = ClientSession(read, write)
            session = await exit_stack.enter_async_context(self.client)
            
            # 初始化Client
            logger.info("[MCPClient] MCP %s：开始初始化会话", mcp_id)
            await asyncio.wait_for(
                session.initialize(),
                timeout=timeout_duration
            )
            logger.info("[MCPClient] MCP %s：初始化成功", mcp_id)
            
        except asyncio.TimeoutError:
            self.error_sign.set()
            self.status = MCPStatus.ERROR
            logger.error("[MCPClient] MCP %s：连接或初始化超时", mcp_id)
            # 清理资源
            try:
                await exit_stack.aclose()
            except Exception:
                pass
            raise ConnectionError(f"MCP {mcp_id} 连接超时")
        except Exception as e:
            self.error_sign.set()
            self.status = MCPStatus.ERROR
            logger.error("[MCPClient] MCP %s：初始化失败: %s", mcp_id, e)
            # 清理资源
            try:
                await exit_stack.aclose()
            except Exception:
                pass
            raise

        self.ready_sign.set()
        self.status = MCPStatus.RUNNING
        
        try:
            # 等待关闭信号
            await self.stop_sign.wait()
            logger.info("[MCPClient] MCP %s：收到停止信号，正在关闭", mcp_id)
        except asyncio.CancelledError:
            logger.info("[MCPClient] MCP %s：任务被取消，开始清理", mcp_id)
        finally:
            # 关闭Client - 在finally块中确保资源清理
            try:
                # 不使用超时，直接关闭以避免取消作用域问题
                await exit_stack.aclose()
                self.status = MCPStatus.STOPPED
                logger.info("[MCPClient] MCP %s：成功关闭", mcp_id)
            except asyncio.CancelledError:
                # 任务被取消是正常情况
                self.status = MCPStatus.STOPPED
                logger.info("[MCPClient] MCP %s：关闭过程中被取消（正常）", mcp_id)
            except RuntimeError as e:
                if "cancel scope" in str(e).lower() or "different task" in str(e).lower():
                    # 这是已知的TaskGroup问题，记录警告但不影响功能
                    self.status = MCPStatus.STOPPED
                    logger.warning("[MCPClient] MCP %s：关闭时遇到TaskGroup问题（已知问题，忽略）", mcp_id)
                else:
                    self.status = MCPStatus.ERROR
                    logger.warning("[MCPClient] MCP %s：关闭时发生运行时错误: %s", mcp_id, e)
            except Exception as e:
                self.status = MCPStatus.ERROR
                logger.warning("[MCPClient] MCP %s：关闭时发生异常: %s", mcp_id, e)

    async def init(self, user_sub: str | None, mcp_id: str, config: MCPServerSSEConfig | MCPServerStdioConfig) -> None:
        """
        初始化 MCP Client类

        初始化MCP Client，并创建MCP Server进程和ClientSession

        :param str user_sub: 用户ID
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
        self.task = asyncio.create_task(self._main_loop(user_sub, mcp_id, config))

        # 等待初始化完成
        try:
            done, pending = await asyncio.wait(
                [asyncio.create_task(self.ready_sign.wait()),
                 asyncio.create_task(self.error_sign.wait())],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # 取消未完成的任务
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            if self.error_sign.is_set():
                self.status = MCPStatus.ERROR
                logger.error("[MCPClient] MCP %s：初始化失败", mcp_id)
                # 检查主任务是否有异常
                if hasattr(self, 'task') and self.task.done():
                    try:
                        self.task.result()  # 这会重新抛出任务中的异常
                    except Exception as task_exc:
                        logger.error("[MCPClient] MCP %s：主任务异常: %s", mcp_id, task_exc)
                        raise task_exc
                raise Exception(f"MCP {mcp_id} 初始化失败")
        except Exception as e:
            # 确保清理任务
            if hasattr(self, 'task') and not self.task.done():
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
            raise

            # 获取工具列表
        self.tools = (await self.client.list_tools()).tools

    async def call_tool(self, tool_name: str, params: dict) -> "CallToolResult":
        """调用MCP Server的工具"""
        return await self.client.call_tool(tool_name, params)

    async def stop(self) -> None:
        """停止MCP Client"""
        if not hasattr(self, 'stop_sign') or not hasattr(self, 'task'):
            logger.warning("[MCPClient] 客户端未初始化，无需停止")
            return
            
        logger.info("[MCPClient] MCP %s：开始停止客户端", self.mcp_id)
        self.stop_sign.set()
        
        try:
            # 等待任务完成，不设置超时以避免取消作用域问题
            await self.task
            logger.info("[MCPClient] MCP %s：客户端已正常停止", self.mcp_id)
        except asyncio.CancelledError:
            logger.info("[MCPClient] MCP %s：任务已被取消", self.mcp_id)
        except Exception as e:
            logger.warning("[MCPClient] MCP %s：停止时发生异常：%s", self.mcp_id, e)
        finally:
            self.status = MCPStatus.STOPPED
