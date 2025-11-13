# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Task相关数据结构定义"""

import uuid
from typing import Any

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

    current_input: dict[str, Any] = Field(description="当前输入数据", default={})
    error_message: str = Field(description="错误信息", default="")
    retry_times: int = Field(description="当前步骤重试次数", default=0)


class AgentHistoryExtra(BaseModel):
    """执行器历史额外数据"""

    step_goal: str = Field(description="步骤目标")


class StepQueueItem(BaseModel):
    """步骤栈中的元素"""

    step_id: uuid.UUID = Field(description="步骤ID")
    step: Step = Field(description="步骤")
    enable_filling: bool | None = Field(description="是否启用填充", default=None)
    to_user: bool | None = Field(description="是否输出给用户", default=None)
