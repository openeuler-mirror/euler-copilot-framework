# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Agent执行器"""

import logging

from pydantic import Field

from apps.llm.reasoning import ReasoningLLM
from apps.scheduler.executor.base import BaseExecutor
from apps.schemas.enum_var import EventType, SpecialCallType, FlowStatus, StepStatus
from apps.scheduler.mcp_agent.host import MCPHost
from apps.scheduler.mcp_agent.plan import MCPPlanner
from apps.scheduler.pool.mcp.client import MCPClient
from apps.schemas.mcp import MCPCollection, MCPTool
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
    mcp_list: list[MCPCollection] = Field(description="MCP服务器列表", default=[])
    mcp_client: dict[str, MCPClient] = Field(
        description="MCP客户端列表，key为mcp_id", default={}
    )
    tool_list: list[MCPTool] = Field(description="MCP工具列表", default=[])
    params: param | None = Field(
        default=None, description="流执行过程中的参数补充", alias="params"
    )
    resoning_llm: ReasoningLLM = Field(
        default=ReasoningLLM(),
        description="推理大模型",
    )

    async def load_state(self) -> None:
        """从数据库中加载FlowExecutor的状态"""
        logger.info("[FlowExecutor] 加载Executor状态")
        # 尝试恢复State
        if self.task.state and self.task.state.flow_status != FlowStatus.INIT:
            self.task.context = await TaskManager.get_context_by_task_id(self.task.id)

    async def load_mcp(self) -> None:
        """加载MCP服务器列表"""
        logger.info("[MCPAgentExecutor] 加载MCP服务器列表")
        # 获取MCP服务器列表
        app = await AppCenterManager.fetch_app_data_by_id(self.agent_id)
        mcp_ids = app.mcp_service
        for mcp_id in mcp_ids:
            mcp_service = await MCPServiceManager.get_mcp_service(mcp_id)
            if self.task.ids.user_sub not in mcp_service.activated:
                logger.warning(
                    "[MCPAgentExecutor] 用户 %s 未启用MCP %s",
                    self.task.ids.user_sub,
                    mcp_id,
                )
                continue

            self.mcp_list.append(mcp_service)
            self.mcp_client[mcp_id] = await MCPHost.get_client(self.task.ids.user_sub, mcp_id)
            self.tool_list.extend(mcp_service.tools)

    async def run(self) -> None:
        """执行MCP Agent的主逻辑"""
        # 初始化MCP服务
        self.load_state()
        self.load_mcp()
