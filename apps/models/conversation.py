# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""对话 数据库表"""

import uuid
from datetime import UTC, datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.constants import NEW_CHAT

from .base import Base


class Conversation(Base):
    """对话"""

    __tablename__ = "framework_conversation"
    userId: Mapped[str] = mapped_column(String(50), ForeignKey("framework_user.id"), nullable=False)  # noqa: N815
    """用户ID"""
    appId: Mapped[uuid.UUID | None] = mapped_column(  # noqa: N815
        UUID(as_uuid=True), ForeignKey("framework_app.id"), nullable=True,
    )
    """对话使用的App的ID"""
    title: Mapped[str] = mapped_column(String(255), default=NEW_CHAT, nullable=False)
    """对话标题"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default_factory=lambda: uuid.uuid4(),
    )
    """对话ID"""
    createdAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True), default_factory=lambda: datetime.now(tz=UTC),
        nullable=False, index=True,
    )
    """对话创建时间"""
    isTemporary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # noqa: N815
    """是否为临时对话"""


class ConvDocAssociated(str, PyEnum):
    """问答对文件的关联类型"""

    QUESTION = "question"
    ANSWER = "answer"


class ConversationDocument(Base):
    """对话所用的临时文件"""

    __tablename__ = "framework_conversation_document"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""
    conversationId: Mapped[uuid.UUID] = mapped_column(  # noqa: N815
        UUID(as_uuid=True), ForeignKey("framework_conversation.id"), nullable=False, index=True,
    )
    """对话ID"""
    documentId: Mapped[uuid.UUID] = mapped_column(  # noqa: N815
        UUID(as_uuid=True), ForeignKey("framework_document.id"), nullable=False, index=True,
    )
    """文件ID"""
    isUnused: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # noqa: N815
    """是否未使用"""
    associated: Mapped[ConvDocAssociated | None] = mapped_column(
        Enum(ConvDocAssociated), nullable=True, default=None,
    )
    """关联类型"""
    recordId: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("framework_record.id"), nullable=True, default=None)  # noqa: N815
    """问答对ID"""
