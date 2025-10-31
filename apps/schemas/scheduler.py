# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""插件、工作流、步骤相关数据结构定义"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from apps.schemas.enum_var import CallOutputType, CallType
from apps.schemas.task import FlowStepHistory


class CallInfo(BaseModel):
    """Call的名称和描述"""
    name: str = Field(description="Call的名称")
    type: CallType = Field(description="Call的类别")
    description: str = Field(description="Call的描述")


class CallIds(BaseModel):
    """Call的ID，来自于Task"""

    task_id: str = Field(description="任务ID")
    flow_id: str = Field(description="Flow ID")
    session_id: str = Field(description="当前用户的Session ID")
    conversation_id: str = Field(description="当前对话ID")
    app_id: str = Field(description="当前应用的ID")
    user_sub: str = Field(description="当前用户的用户ID")


class CallVars(BaseModel):
    """由Executor填充的变量，即“系统变量”"""

    summary: str = Field(description="上下文信息")
    question: str = Field(description="改写后的用户输入")
    history: dict[str, FlowStepHistory] = Field(description="Executor中历史工具的结构化数据", default={})
    history_order: list[str] = Field(description="Executor中历史工具的顺序", default=[])
    ids: CallIds = Field(description="Call的ID")


class CallTokens(BaseModel):
    """Call的Tokens"""

    input_tokens: int = Field(description="输入的Tokens", default=0)
    output_tokens: int = Field(description="输出的Tokens", default=0)


class ExecutorBackground(BaseModel):
    """Executor的背景信息"""

    conversation: list[dict[str, str]] = Field(description="对话记录")
    facts: list[str] = Field(description="当前Executor的背景信息")
    enable_thinking: bool = Field(description="是否启用思维链", default=False)


class CallError(Exception):
    """Call错误"""

    def __init__(self, message: str, data: dict[str, Any]) -> None:
        """获取Call错误中的数据"""
        self.message = message
        self.data = data


class CallOutputChunk(BaseModel):
    """Call的输出"""

    type: CallOutputType = Field(description="输出类型")
    content: str | dict[str, Any] = Field(description="输出内容")
