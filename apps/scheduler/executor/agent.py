# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Agent执行器"""

import logging

from pydantic import Field

from apps.scheduler.executor.base import BaseExecutor
from apps.schemas.enum_var import EventType, SpecialCallType, FlowStatus, StepStatus
from apps.scheduler.mcp_agent import host, plan, select
from apps.schemas.mcp import MCPServerConfig, MCPTool
from apps.schemas.task import ExecutorState, StepQueueItem
from apps.schemas.message import param
from apps.services.task import TaskManager
from apps.services.appcenter import AppCenterManager
from apps.services.mcp_service import MCPServiceManager
logger = logging.getLogger(__name__)


class MCPAgentExecutor(BaseExecutor):
    """MCP Agent执行器"""

    max_steps: int = Field(default=20, description="最大步数")
    servers_id: list[str] = Field(description="MCP server id")
    agent_id: str = Field(default="", description="Agent ID")
    agent_description: str = Field(default="", description="Agent描述")
    mcp_list: list[MCPServerConfig] = Field(description="MCP服务器列表", default=[])
    tool_list: list[MCPTool] = Field(description="MCP工具列表", default=[])
    params: param | None = Field(
        default=None, description="流执行过程中的参数补充", alias="params"
    )

    async def load_mcp_list(self) -> None:
        """加载MCP服务器列表"""
        logger.info("[MCPAgentExecutor] 加载MCP服务器列表")
        # 获取MCP服务器列表
        app = await AppCenterManager.fetch_app_data_by_id(self.agent_id)
        mcp_ids = app.mcp_service
        for mcp_id in mcp_ids:
            self.mcp_list.append(
                await MCPServiceManager.get_mcp_service(mcp_id)
            )

    async def load_tools(self) -> None:
        """加载MCP工具列表"""
        logger.info("[MCPAgentExecutor] 加载MCP工具列表")
        # 获取工具列表
        mcp_ids = [mcp.id for mcp in self.mcp_list]
        for mcp_id in mcp_ids:
            if not await MCPServiceManager.is_mcp_enabled(mcp_id, self.agent_id):
                logger.warning("MCP %s 未启用，跳过工具加载", mcp_id)
                continue
            # 获取MCP工具
            tools = await MCPServiceManager.get_mcp_tools(mcp_id)
            self.tool_list.extend(tools)

    async def load_state(self) -> None:
        """从数据库中加载FlowExecutor的状态"""
        logger.info("[FlowExecutor] 加载Executor状态")
        # 尝试恢复State
        if self.task.state and self.task.state.flow_status != FlowStatus.INIT:
            self.task.context = await TaskManager.get_context_by_task_id(self.task.id)

    async def run(self) -> None:
        """执行MCP Agent的主逻辑"""
        # 初始化MCP服务
