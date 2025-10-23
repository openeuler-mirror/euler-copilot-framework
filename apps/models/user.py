# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户表"""

import enum
import uuid
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class User(Base):
    """用户表"""

    __tablename__ = "framework_user"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """用户ID"""
    userSub: Mapped[str] = mapped_column(String(50), index=True, unique=True, nullable=False)  # noqa: N815
    """用户名"""
    lastLogin: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True), default_factory=lambda: datetime.now(tz=UTC), nullable=False,
    )
    """用户最后一次登录时间"""
    isActive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # noqa: N815
    """用户是否活跃"""
    isWhitelisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # noqa: N815
    """用户是否白名单"""
    credit: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    """用户风控分"""
    personalToken: Mapped[str] = mapped_column(  # noqa: N815
        String(100), default_factory=lambda: sha256(str(uuid.uuid4()).encode()).hexdigest()[:16], nullable=False,
    )
    """用户个人令牌"""
    autoExecute: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)  # noqa: N815
    """Agent是否自动执行"""


class UserFavoriteType(str, enum.Enum):
    """用户收藏类型"""

    APP = "app"
    SERVICE = "service"


class UserFavorite(Base):
    """用户收藏"""

    __tablename__ = "framework_user_favorite"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """用户收藏ID"""
    userSub: Mapped[str] = mapped_column(String(50), ForeignKey("framework_user.userSub"), index=True, nullable=False)  # noqa: N815
    """用户名"""
    favouriteType: Mapped[UserFavoriteType] = mapped_column(Enum(UserFavoriteType), nullable=False)  # noqa: N815
    """收藏类型"""
    itemId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)  # noqa: N815
    """收藏项目ID（App/Service ID）"""


class UserAppUsage(Base):
    """用户应用使用情况"""

    __tablename__ = "framework_user_app_usage"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """用户应用使用情况ID"""
    userSub: Mapped[str] = mapped_column(String(50), ForeignKey("framework_user.userSub"), unique=True, nullable=False)  # noqa: N815
    """用户名"""
    appId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("framework_app.id"), nullable=False)  # noqa: N815
    """应用ID"""
    usageCount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # noqa: N815
    """应用使用次数"""
    lastUsed: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True), default_factory=lambda: datetime.now(tz=UTC), nullable=False,
    )
    """用户最后一次使用时间"""


class UserTag(Base):
    """用户标签"""

    __tablename__ = "framework_user_tag"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """用户标签ID"""
    userSub: Mapped[str] = mapped_column(String(50), ForeignKey("framework_user.userSub"), unique=True, nullable=False)  # noqa: N815
    """用户名"""
    tag: Mapped[int] = mapped_column(BigInteger, ForeignKey("framework_tag.id"), nullable=False)
    """标签ID"""
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    """标签归类次数"""
