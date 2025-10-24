# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""评论 数据库表"""

import uuid
from datetime import UTC, datetime
from enum import Enum as PyEnum

from sqlalchemy import ARRAY, BigInteger, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CommentType(str, PyEnum):
    """点赞点踩类型"""

    LIKE = "liked"
    DISLIKE = "disliked"
    NONE = "none"


class Comment(Base):
    """评论"""

    __tablename__ = "framework_comment"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""
    recordId: Mapped[uuid.UUID] = mapped_column(  # noqa: N815
        UUID(as_uuid=True), ForeignKey("framework_record.id"), nullable=False, index=True,
    )
    """问答对ID"""
    userId: Mapped[str] = mapped_column(String(50), ForeignKey("framework_user.id"), nullable=False)  # noqa: N815
    """用户ID"""
    commentType: Mapped[CommentType] = mapped_column(Enum(CommentType), nullable=False)  # noqa: N815
    """点赞点踩"""
    feedbackType: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False)  # noqa: N815
    """投诉类别"""
    feedbackLink: Mapped[str] = mapped_column(String(1000), nullable=False)  # noqa: N815
    """投诉链接"""
    feedbackContent: Mapped[str] = mapped_column(String(1000), nullable=False)  # noqa: N815
    """投诉内容"""
    createdAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True), default_factory=lambda: datetime.now(tz=UTC),
        nullable=False,
    )
    """评论创建时间"""
