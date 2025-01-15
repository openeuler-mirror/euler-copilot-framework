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

    step_name: str
    step_status: StepStatus
    step_order: str
    input: dict[str, Any]
    output: dict[str, Any]


class RecordFlow(BaseModel):
    """Flow的执行信息"""

    id: str
    record_id: str
    plugin_id: str
    flow_id: str
    step_num: int
    steps: list[RecordFlowStep]


class RecordData(BaseModel):
    """GET /api/record/{conversation_id} Result内元素数据结构"""

    id: str
    group_id: str
    conversation_id: str
    task_id: str
    document: list[RecordDocument] = []
    flow: Optional[RecordFlow] = None
    content: RecordContent
    metadata: RecordMetadata
    created_at: float
