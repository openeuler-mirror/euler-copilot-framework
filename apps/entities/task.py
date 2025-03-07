"""Task相关数据结构定义

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from apps.entities.enum import StepStatus
from apps.entities.record import RecordData


class FlowHistory(BaseModel):
    """任务执行历史；每个Executor每个步骤执行后都会创建

    Collection: flow_history
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    task_id: str = Field(description="任务ID")
    flow_id: str = Field(description="FlowID")
    plugin_id: str = Field(description="插件ID")
    step_name: str = Field(description="当前步骤名称")
    step_order: str = Field(description="当前步骤进度")
    status: StepStatus = Field(description="当前步骤状态")
    input_data: dict[str, Any] = Field(description="当前Step执行的输入", default={})
    output_data: dict[str, Any] = Field(description="当前Step执行后的结果", default={})
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=timezone.utc).timestamp(), 3))


class ExecutorState(BaseModel):
    """FlowExecutor状态"""

    # 执行器级数据
    name: str = Field(description="执行器名称")
    description: str = Field(description="执行器描述")
    status: StepStatus = Field(description="执行器状态")
    # 附加信息
    step_name: str = Field(description="当前步骤名称")
    plugin_id: str = Field(description="插件ID")
    # 运行时数据
    thought: str = Field(description="大模型的思考内容", default="")
    slot_data: dict[str, Any] = Field(description="待使用的参数", default={})
    remaining_schema: dict[str, Any] = Field(description="待填充参数的JSON Schema", default={})


class TaskBlock(BaseModel):
    """内存中的Task块，不存储在数据库中"""

    session_id: str = Field(description="浏览器会话ID")
    record: RecordData = Field(description="当前任务执行过程关联的Record")
    flow_state: Optional[ExecutorState] = Field(description="Flow的状态", default=None)
    flow_context: dict[str, FlowHistory] = Field(description="Flow的执行信息", default={})
    new_context: list[str] = Field(description="Flow的执行信息（增量ID）", default=[])


class RequestDataPlugin(BaseModel):
    """POST /api/chat的plugins字段数据"""

    plugin_id: str = Field(description="插件ID")
    flow_id: str = Field(description="Flow ID")
    params: dict[str, Any] = Field(description="插件参数")
    auth: dict[str, Any] = Field(description="插件鉴权信息")


class Task(BaseModel):
    """任务信息

    Collection: task
    外键：task - record_group
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    conversation_id: str
    record_groups: list[str] = []
    state: Optional[ExecutorState] = Field(description="Flow的状态", default=None)
    ended: bool = False
    updated_at: float = Field(default_factory=lambda: round(datetime.now(tz=timezone.utc).timestamp(), 3))
