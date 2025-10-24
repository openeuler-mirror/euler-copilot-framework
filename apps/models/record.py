# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问答对 数据库表"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Record(Base):
    """问答对"""

    __tablename__ = "framework_record"
    userId: Mapped[str] = mapped_column(String(50), ForeignKey("framework_user.id"), nullable=False)  # noqa: N815
    """用户ID"""
    conversationId: Mapped[uuid.UUID] = mapped_column(    # noqa: N815
        UUID(as_uuid=True), ForeignKey("framework_conversation.id"), nullable=False,
    )
    """对话ID"""
    taskId: Mapped[uuid.UUID | None] = mapped_column(  # noqa: N815
        UUID(as_uuid=True), ForeignKey("framework_task.id"), nullable=True,
    )
    """任务ID"""
    content: Mapped[str] = mapped_column(Text, nullable=False)
    """问答对数据"""
    key: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    """问答对密钥"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default_factory=lambda: uuid.uuid4(),
    )
    """问答对ID"""
    createdAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True), default_factory=lambda: datetime.now(tz=UTC), nullable=False,
    )
    """问答对创建时间"""


class RecordMetadata(Base):
    """问答对元数据"""

    __tablename__ = "framework_record_metadata"
    recordId: Mapped[uuid.UUID] = mapped_column(  # noqa: N815
        UUID(as_uuid=True), ForeignKey("framework_record.id"), primary_key=True,
    )
    """问答对ID"""
    timeCost: Mapped[float] = mapped_column(Float, default=0, nullable=False)  # noqa: N815
    """问答对耗时"""
    inputTokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # noqa: N815
    """问答对输入token数"""
    outputTokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # noqa: N815
    """问答对输出token数"""
    featureSwitch: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, nullable=False)  # noqa: N815
    """问答对功能开关"""
