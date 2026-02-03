# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Task相关数据结构定义"""

import uuid

from pydantic import BaseModel, Field

from apps.models.task import ExecutorCheckpoint, ExecutorHistory, Task, TaskRuntime

from .flow import Step


class TaskData(BaseModel):
    """任务数据"""

    metadata: Task = Field(description="任务")
    runtime: TaskRuntime = Field(description="任务运行时数据")
    state: ExecutorCheckpoint | None = Field(description="执行状态")
    context: list[ExecutorHistory] = Field(description="执行历史")


class AgentCheckpointExtra(BaseModel):
    """Executor额外数据"""

    todo_list: str = Field(description="TODO列表", default="")
    step_count: int = Field(description="步骤计数", default=0)
    tool_list: list[str] | None = Field(description="工具列表", default=None)


class AgentHistoryExtra(BaseModel):
    """执行器历史额外数据"""

    tool_call_id: str | None = Field(description="工具调用ID", default=None)
    role: str | None = Field(description="消息角色", default=None)
    risk_confirmed: bool | None = Field(description="风险已确认", default=None)


class StepQueueItem(BaseModel):
    """步骤栈中的元素"""

    step_id: uuid.UUID = Field(description="步骤ID")
    step: Step = Field(description="步骤")
    enable_filling: bool | None = Field(description="是否启用填充", default=None)
    to_user: bool | None = Field(description="是否输出给用户", default=None)
