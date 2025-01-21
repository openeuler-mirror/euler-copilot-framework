"""Record数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from apps.entities.collection import (
    Document,
    RecordContent,
    RecordMetadata,
)
from apps.entities.enum_var import StepStatus


class RecordDocument(Document):
    """GET /api/record/{conversation_id} Result中的document数据结构"""

    id: str = Field(alias="_id", default="")
    user_sub: None = None
    associated: Literal["question", "answer"]

    class Config:
        """配置"""

        populate_by_name = True


class RecordFlowStep(BaseModel):
    """Record表子项：flow的单步数据结构"""

    step_id: str = Field(alias="stepId")
    step_status: StepStatus = Field(alias="stepStatus")
    input: dict[str, Any]
    output: dict[str, Any]


class RecordFlow(BaseModel):
    """Flow的执行信息"""

    id: str
    record_id: str = Field(alias="recordId")
    flow_id: str = Field(alias="flowId")
    step_num: int = Field(alias="stepNum")
    steps: list[RecordFlowStep]


class RecordData(BaseModel):
    """GET /api/record/{conversation_id} Result内元素数据结构"""

    id: str
    group_id: str = Field(alias="groupId")
    conversation_id: str = Field(alias="conversationId")
    task_id: str = Field(alias="taskId")
    document: list[RecordDocument] = []
    flow: Optional[RecordFlow] = None
    content: RecordContent
    metadata: RecordMetadata
    created_at: float = Field(alias="createdAt")
