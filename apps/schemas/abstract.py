# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""摘要数据结构"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AbstractData(BaseModel):
    """摘要数据结构（适配数据库Abstract表）"""

    id: uuid.UUID | None = Field(default=None, description="摘要记录ID")
    record_id: uuid.UUID | None = Field(default=None, alias="recordId",description="关联的记录ID")
    title: str | None = Field(default=None, description="摘要标题")
    abstract: str = Field(default="", alias="recordAbstract",description="记录的摘要内容")
    created_at: datetime | None = Field(default=None, alias="createdAt",description="摘要创建时间（UTC）")

    model_config = ConfigDict(from_attributes=True)
