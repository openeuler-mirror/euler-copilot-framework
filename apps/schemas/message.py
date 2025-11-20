# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""队列中的消息结构"""

import uuid
from typing import Any

from pydantic import BaseModel, Field

from apps.models import ExecutorStatus, StepStatus
from apps.schemas.enum_var import EventType

from .record import RecordMetadata


class FlowParams(BaseModel):
    """流执行过程中的参数补充"""

    content: dict[str, Any] = Field(default={}, description="流执行过程中的参数补充内容")
    description: str = Field(default="", description="流执行过程中的参数补充描述")


class HeartbeatData(BaseModel):
    """心跳事件的数据结构"""

    event: str = Field(
        default=EventType.HEARTBEAT.value, description="支持的事件类型",
    )


class MessageExecutor(BaseModel):
    """消息中有关Flow信息的部分"""

    app_id: uuid.UUID | None = Field(description="插件ID", alias="appId", default=None)
    executor_id: str = Field(description="Flow ID", alias="executorId")
    executor_name: str = Field(description="Flow名称", alias="executorName")
    executor_status: ExecutorStatus = Field(
        description="Flow状态", alias="executorStatus", default=ExecutorStatus.INIT,
    )
    step_id: uuid.UUID = Field(description="当前步骤ID", alias="stepId")
    step_name: str = Field(description="当前步骤名称", alias="stepName")
    step_type: str = Field(description="当前步骤类型", alias="stepType")
    step_status: StepStatus = Field(description="当前步骤状态", alias="stepStatus")


class TextAddContent(BaseModel):
    """text.add消息的content"""

    text: str = Field(min_length=1, description="流式生成的文本内容")


class MessageBase(HeartbeatData):
    """基础消息事件结构"""

    id: uuid.UUID
    conversation_id: uuid.UUID | None = Field(alias="conversationId", default=None)
    flow: MessageExecutor | None = None
    content: Any | None = Field(default=None, description="消息内容")
    metadata: RecordMetadata
