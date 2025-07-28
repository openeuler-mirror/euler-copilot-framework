# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Agent执行器"""

import logging

from pydantic import Field

from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.mcp_agent.agent.mcp import MCPAgent
from apps.schemas.task import ExecutorState, StepQueueItem
from apps.services.task import TaskManager

logger = logging.getLogger(__name__)


class MCPAgentExecutor(BaseExecutor):
    """MCP Agent执行器"""

    question: str = Field(description="用户输入")
    max_steps: int = Field(default=20, description="最大步数")
    servers_id: list[str] = Field(description="MCP server id")
    agent_id: str = Field(default="", description="Agent ID")
    agent_description: str = Field(default="", description="Agent描述")

    async def load_state(self) -> None:
        """从数据库中加载FlowExecutor的状态"""
        logger.info("[FlowExecutor] 加载Executor状态")
        # 尝试恢复State
        if self.task.state:
            context_objects = await TaskManager.get_context_by_task_id(self.task.id)
            # 将对象转换为字典以保持与系统其他部分的一致性
            self.task.context = [context.model_dump(exclude_none=True, by_alias=True) for context in context_objects]
