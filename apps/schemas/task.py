# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Task相关数据结构定义"""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from apps.llm.enum import DefaultModelId
from apps.schemas.enum_var import FlowStatus, StepStatus, LanguageType
from apps.schemas.flow import Step
from apps.schemas.mcp import MCPPlan


class FlowStepHistory(BaseModel):
    """
    任务执行历史；每个Executor每个步骤执行后都会创建

    Collection: flow_history
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    task_id: str = Field(description="任务ID")
    flow_id: str = Field(description="FlowID")
    flow_name: str = Field(description="Flow名称")
    flow_status: FlowStatus = Field(description="Flow状态")
    step_id: str = Field(description="当前步骤名称")
    step_name: str = Field(description="当前步骤名称")
    step_description: str = Field(description="当前步骤描述", default="")
    step_status: StepStatus = Field(description="当前步骤状态")
    input_data: dict[str, Any] = Field(description="当前Step执行的输入", default={})
    output_data: dict[str, Any] = Field(description="当前Step执行后的结果", default={})
    ex_data: dict[str, Any] | None = Field(description="额外数据", default=None)
    created_at: float = Field(default_factory=lambda: round(
        datetime.now(tz=UTC).timestamp(), 3))


class ExecutorState(BaseModel):
    """FlowExecutor状态"""

    # 执行器级数据
    flow_id: str = Field(description="Flow ID", default="")
    flow_name: str = Field(description="Flow名称", default="")
    description: str = Field(description="Flow描述", default="")
    flow_status: FlowStatus = Field(
        description="Flow状态", default=FlowStatus.INIT)
    # 任务级数据
    step_cnt: int = Field(description="当前步骤数量", default=0)
    step_id: str = Field(description="当前步骤ID", default="")
    tool_id: str = Field(description="当前工具ID", default="")
    step_name: str = Field(description="当前步骤名称", default="")
    step_status: StepStatus = Field(
        description="当前步骤状态", default=StepStatus.UNKNOWN)
    step_description: str = Field(description="当前步骤描述", default="")
    app_id: str = Field(description="应用ID", default="")
    current_input: dict[str, Any] = Field(description="当前输入数据", default={})
    error_message: str = Field(description="错误信息", default="")
    error_info: dict[str, Any] | None = Field(
        description="详细错误信息", default=None)
    retry_times: int = Field(description="当前步骤重试次数", default=0)


class TaskIds(BaseModel):
    """任务涉及的各种ID"""

    session_id: str = Field(description="会话ID")
    group_id: str = Field(description="组ID")
    conversation_id: str = Field(description="对话ID")
    record_id: str = Field(
        description="记录ID", default_factory=lambda: str(uuid.uuid4()))
    user_sub: str = Field(description="用户ID")
    active_id: str = Field(
        description="活动ID", default_factory=lambda: str(uuid.uuid4()))
    func_call_llm_id: str = Field(
        description="函数调用大模型ID", default=DefaultModelId.DEFAULT_FUNCTION_CALL_MODEL_ID.value)
    chat_llm_id: str = Field(
        description="聊天大模型ID", default=DefaultModelId.DEFAULT_CHAT_MODEL_ID.value)
    embedding_llm_id: str = Field(
        description="向量化大模型ID", default=DefaultModelId.DEFAULT_EMBEDDING_MODEL_ID.value)
    reranker_llm_id: str = Field(
        description="重排序大模型ID", default=DefaultModelId.DEFAULT_RERANKER_MODEL_ID.value)


class TaskTokens(BaseModel):
    """任务Token"""

    input_tokens: int = Field(description="输入Token", default=0)
    output_tokens: int = Field(description="输出Token", default=0)
    time: float = Field(description="时间点", default=0.0)
    full_time: float = Field(description="完整时间成本", default=0.0)
    documents: list[dict[str, Any]] = Field(description="文档列表", default=[])


class TaskRuntime(BaseModel):
    """任务运行时数据"""

    question: str = Field(description="用户问题", default="")
    answer: str = Field(description="模型回答", default="")
    facts: list[str] = Field(description="记忆", default=[])
    summary: str = Field(description="摘要", default="")
    filled: dict[str, Any] = Field(description="填充的槽位", default={})
    documents: list[dict[str, Any]] = Field(description="文档列表", default=[])
    temporary_plans: MCPPlan | None = Field(description="临时计划列表", default=None)


class Task(BaseModel):
    """
    任务信息

    Collection: task
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    ids: TaskIds = Field(description="任务涉及的各种ID")
    context: list[FlowStepHistory] = Field(
        description="Flow的步骤执行信息", default=[])
    state: ExecutorState = Field(
        description="Flow的状态", default=ExecutorState())
    tokens: TaskTokens = Field(description="Token信息")
    runtime: TaskRuntime = Field(description="任务运行时数据")
    created_at: float = Field(default_factory=lambda: round(
        datetime.now(tz=UTC).timestamp(), 3))
    language: LanguageType = Field(
        description="语言", default=LanguageType.CHINESE)


class StepQueueItem(BaseModel):
    """步骤栈中的元素"""

    step_id: str = Field(description="步骤ID")
    step: Step = Field(description="步骤")
    enable_filling: bool | None = Field(description="是否启用填充", default=None)
    to_user: bool | None = Field(description="是否输出给用户", default=None)
