# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""插件、工作流、步骤相关数据结构定义"""

import uuid
from typing import Any

from pydantic import BaseModel, Field

from apps.models import ExecutorHistory, LanguageType

from .enum_var import CallOutputType


class CallInfo(BaseModel):
    """Call的名称和描述"""

    name: str = Field(description="Call的名称")
    description: str = Field(description="Call的描述")


class CallIds(BaseModel):
    """Call的ID，来自于Task"""

    task_id: uuid.UUID = Field(description="任务ID")
    executor_id: str = Field(description="Flow ID")
    auth_header: str | None = Field(description="当前用户的Authorization Header")
    app_id: uuid.UUID | None = Field(description="当前应用的ID")
    user_id: str = Field(description="当前用户的用户ID")
    conversation_id: uuid.UUID | None = Field(description="当前对话的ID")


class ExecutorBackground(BaseModel):
    """Executor的背景信息"""

    num: int = Field(description="对话记录最大数量", default=0)
    conversation: list[dict[str, str]] = Field(description="对话记录", default=[])
    facts: list[str] = Field(description="当前Executor的背景信息", default=[])
    history_questions: list[str] = Field(description="历史问题列表", default=[])


class CallVars(BaseModel):
    """由Executor填充的变量，即“系统变量”"""

    thinking: str = Field(description="上下文信息")
    question: str = Field(description="改写后的用户输入")
    step_data: dict[uuid.UUID, ExecutorHistory] = Field(description="Executor中历史工具的结构化数据", default={})
    step_order: list[uuid.UUID] = Field(description="Executor中历史工具的顺序", default=[])
    background: ExecutorBackground = Field(description="Executor的背景信息")
    ids: CallIds = Field(description="Call的ID")
    language: LanguageType = Field(description="语言", default=LanguageType.CHINESE)
    app_metadata: Any = Field(description="应用元数据", default=None)


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


class TopFlow(BaseModel):
    """最匹配用户输入的Flow"""

    choice: str = Field(description="最匹配用户输入的Flow的名称")
