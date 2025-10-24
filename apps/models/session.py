# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""会话相关 数据库表"""

import secrets
from datetime import UTC, datetime, timedelta
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SessionType(PyEnum):
    """会话类型"""

    ACCESS_TOKEN = "access_token"  # noqa: S105
    REFRESH_TOKEN = "refresh_token"  # noqa: S105
    PLUGIN_TOKEN = "plugin_token"  # noqa: S105
    CODE = "code"


class Session(Base):
    """会话"""

    __tablename__ = "framework_session"
    userId: Mapped[str] = mapped_column(String(50), ForeignKey("framework_user.id"), nullable=False)  # noqa: N815
    """用户ID"""
    ip: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    """IP地址"""
    pluginId: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)  # noqa: N815
    """(AccessToken) 插件ID"""
    token: Mapped[str | None] = mapped_column(String(2000), nullable=True, default=None)
    """(AccessToken) Token信息"""
    validUntil: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=UTC) + timedelta(days=30),
    )
    """有效期"""
    id: Mapped[str] = mapped_column(String(255), primary_key=True, default_factory=lambda: secrets.token_hex(16))
    """会话ID"""
    sessionType: Mapped[SessionType] = mapped_column(  # noqa: N815
        Enum(SessionType), default=SessionType.ACCESS_TOKEN, nullable=False,
    )
    """会话类型"""


class SessionActivity(Base):
    """会话活动"""

    __tablename__ = "framework_session_activity"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""
    userId: Mapped[str] = mapped_column(String(50), ForeignKey("framework_user.id"), nullable=False)  # noqa: N815
    """用户ID"""
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    """时间戳"""
