"""插件、工作流、步骤相关数据结构定义

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field

from apps.common.queue import MessageQueue
from apps.entities.task import FlowHistory, RequestDataPlugin


class Step(BaseModel):
    """Flow中Step的数据"""

    name: str
    confirm: bool = False
    call_type: str
    params: dict[str, Any] = {}
    next: Optional[str] = None

class NextFlow(BaseModel):
    """Flow中“下一步”的数据格式"""

    id: str
    plugin: Optional[str] = None
    question: Optional[str] = None

class Flow(BaseModel):
    """Flow（工作流）的数据格式"""

    on_error: Optional[Step] = Step(
        name="error",
        call_type="llm",
        params={
            "user_prompt": "当前工具执行发生错误，原始错误信息为：{data}. 请向用户展示错误信息，并给出可能的解决方案。\n\n背景信息：{context}",
        },
    )
    steps: dict[str, Step]
    next_flow: Optional[list[NextFlow]] = None


class PluginData(BaseModel):
    """插件数据格式"""

    id: str
    name: str
    description: str
    auth: dict[str, Any] = {}


class CallResult(BaseModel):
    """Call运行后的返回值"""

    message: str = Field(description="经LLM理解后的Call的输出")
    output: dict[str, Any] = Field(description="Call的原始输出")
    output_schema: dict[str, Any] = Field(description="Call中Output对应的Schema")
    extra: Optional[dict[str, Any]] = Field(description="Call的额外输出", default=None)


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

    conversation: list[dict[str, str]] = Field(description="当前Executor的上下文对话")
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
    plugin_data: RequestDataPlugin = Field(description="传递给Executor中Call的参数")
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
