"""插件、工作流、步骤相关数据结构定义

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

from pydantic import BaseModel, Field

from apps.entities.task import FlowStepHistory


class CallVars(BaseModel):
    """所有Call都需要接受的参数。包含用户输入、上下文信息、Step的输出记录等

    这一部分的参数由Executor填充，用户无法修改
    """

    summary: str = Field(description="上下文信息")
    question: str = Field(description="改写后的用户输入")
    history: dict[str, FlowStepHistory] = Field(description="Executor中历史工具的结构化数据", default=[])
    task_id: str = Field(description="任务ID")
    flow_id: str = Field(description="Flow ID")
    session_id: str = Field(description="当前用户的Session ID")


class ExecutorBackground(BaseModel):
    """Executor的背景信息"""

    conversation: str = Field(description="当前Executor的背景信息")
    facts: list[str] = Field(description="当前Executor的背景信息")


class CallError(Exception):
    """Call错误"""

    def __init__(self, message: str, data: dict[str, Any]) -> None:
        """获取Call错误中的数据"""
        self.message = message
        self.data = data
