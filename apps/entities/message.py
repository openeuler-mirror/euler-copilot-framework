"""队列中的消息结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field

from apps.entities.collection import RecordMetadata
from apps.entities.enum import EventType, FlowOutputType, StepStatus


class HeartbeatData(BaseModel):
    """心跳事件的数据结构"""

    event: EventType = Field(
        default=EventType.HEARTBEAT, description="支持的事件类型",
    )


class MessageFlow(BaseModel):
    """消息中有关Flow信息的部分"""

    plugin_id: str = Field(description="插件ID")
    flow_id: str = Field(description="Flow ID")
    step_name: str = Field(description="当前步骤名称")
    step_status: StepStatus = Field(description="当前步骤状态")
    step_progress: str = Field(description="当前步骤进度，例如1/4")


class MessageMetadata(RecordMetadata):
    """消息的元数据"""

    feature: None = None


class InitContentFeature(BaseModel):
    """init消息的feature"""

    max_tokens: int = Field(description="最大生成token数", ge=0)
    context_num: int = Field(description="上下文消息数量", le=10, ge=0)
    enable_feedback: bool = Field(description="是否启用反馈")
    enable_regenerate: bool = Field(description="是否启用重新生成")


class InitContent(BaseModel):
    """init消息的content"""

    feature: InitContentFeature = Field(description="问答功能开关")
    created_at: float = Field(description="创建时间")


class TextAddContent(BaseModel):
    """text.add消息的content"""

    text: str = Field(min_length=1, description="流式生成的文本内容")


class DocumentAddContent(BaseModel):
    """document.add消息的content"""

    document_id: str = Field(min_length=36, max_length=36, description="文档UUID")
    document_name: str = Field(description="文档名称")
    document_type: str = Field(description="文档MIME类型")
    document_size: float = Field(ge=0, description="文档大小，单位是KB，保留两位小数")


class SuggestContent(BaseModel):
    """suggest消息的content"""

    plugin_id: str = Field(description="插件ID")
    flow_id: str = Field(description="Flow ID")
    flow_description: str = Field(description="Flow描述")
    question: str = Field(description="用户问题")


class FlowStartContent(BaseModel):
    """flow.start消息的content"""

    question: str = Field(description="用户问题")
    params: dict[str, Any] = Field(description="预先提供的参数")


class StepInputContent(BaseModel):
    """step.input消息的content"""

    call_type: str = Field(description="Call类型")
    params: dict[str, Any] = Field(description="Step最后输入的参数")


class StepOutputContent(BaseModel):
    """step.output消息的content"""

    call_type: str = Field(description="Call类型")
    message: str = Field(description="LLM大模型输出的自然语言文本")
    output: dict[str, Any] = Field(description="Step输出的结构化数据")


class FlowStopContent(BaseModel):
    """flow.stop消息的content"""

    type: FlowOutputType = Field(description="Flow输出的类型")
    data: Optional[dict[str, Any]] = Field(description="Flow输出的数据")


class MessageBase(HeartbeatData):
    """基础消息事件结构"""

    id: str = Field(min_length=36, max_length=36)
    group_id: str = Field(min_length=36, max_length=36)
    conversation_id: str = Field(min_length=36, max_length=36)
    task_id: str = Field(min_length=36, max_length=36)
    flow: Optional[MessageFlow] = None
    content: dict[str, Any] = {}
    metadata: MessageMetadata
