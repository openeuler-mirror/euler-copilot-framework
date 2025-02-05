"""插件、工作流、步骤相关数据结构定义

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

from pydantic import BaseModel, Field

from apps.common.queue import MessageQueue
from apps.entities.task import FlowHistory, RequestDataApp


class SysCallVars(BaseModel):
    """所有Call都需要接受的参数。包含用户输入、上下文信息、Step的输出记录等

    这一部分的参数由Executor填充，用户无法修改
    """

    background: str = Field(description="上下文信息")
    question: str = Field(description="改写后的用户输入")
    history: list[FlowHistory] = Field(description="Executor中历史工具的结构化数据", default=[])
    task_id: str = Field(description="任务ID")
    session_id: str = Field(description="当前用户的Session ID")
    extra: dict[str, Any] = Field(description="其他Executor设置的、用户不可修改的参数", default={})


class ExecutorBackground(BaseModel):
    """Executor的背景信息"""

    conversation: list[dict[str, str]] = Field(description="当前Executor的背景信息")
    facts: list[str] = Field(description="当前Executor的背景信息")
    thought: str = Field(description="之前Executor的思考内容", default="")


class SysExecVars(BaseModel):
    """Executor状态

    由系统自动传递给Executor
    """

    queue: MessageQueue = Field(description="当前Executor关联的Queue")
    question: str = Field(description="当前Agent的目标")
    task_id: str = Field(description="当前Executor关联的TaskID")
    session_id: str = Field(description="当前用户的Session ID")
    app_data: RequestDataApp = Field(description="传递给Executor中Call的参数")
    background: ExecutorBackground = Field(description="当前Executor的背景信息")

    class Config:
        """允许任意类型"""

        arbitrary_types_allowed = True


class CallError(Exception):
    """Call错误"""

    def __init__(self, message: str, data: dict[str, Any]) -> None:
        """获取Call错误中的数据"""
        self.message = message
        self.data = data
