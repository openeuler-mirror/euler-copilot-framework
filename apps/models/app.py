# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""应用 数据库表"""

import uuid
from datetime import UTC, datetime
from enum import Enum as PyEnum
from typing import Any, ClassVar

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AppType(str, PyEnum):
    """应用中心应用类型"""

    FLOW = "flow"
    AGENT = "agent"


class PermissionType(str, PyEnum):
    """权限类型"""

    PROTECTED = "protected"
    PUBLIC = "public"
    PRIVATE = "private"


class App(Base):
    """应用"""

    __tablename__ = "framework_app"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """应用名称"""
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    """应用描述"""
    authorId: Mapped[str] = mapped_column(String(50), ForeignKey("framework_user.id"), nullable=False)  # noqa: N815
    """应用作者ID"""
    appType: Mapped[AppType] = mapped_column(Enum(AppType), nullable=False)  # noqa: N815
    """应用类型"""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4)
    """应用ID"""
    updatedAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=UTC),
        onupdate=lambda: datetime.now(tz=UTC),
        index=True,
        nullable=False,
    )
    """应用更新时间"""
    icon: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    """应用图标路径"""
    isPublished: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # noqa: N815
    """是否发布"""
    permission: Mapped[PermissionType] = mapped_column(
        Enum(PermissionType), default=PermissionType.PUBLIC, nullable=False,
    )
    """权限类型"""
    # 索引
    idx_published_updated_at: ClassVar[Index] = Index("idx_published_updated_at", "isPublished", "updatedAt")
    idx_author_id_name: ClassVar[Index] = Index("idx_author_id_name", "authorId", "id", "name")

    __table_args__: ClassVar[tuple[Any, ...]] = (
        idx_published_updated_at,
        idx_author_id_name,
        {"extend_existing": True},
    )


class AppACL(Base):
    """应用权限"""

    __tablename__ = "framework_app_acl"
    appId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("framework_app.id"), primary_key=True)  # noqa: N815
    """关联的应用ID"""
    userId: Mapped[str] = mapped_column(String(50), ForeignKey("framework_user.id"), nullable=False, index=True)  # noqa: N815
    """用户ID"""
    action: Mapped[str] = mapped_column(String(255), default="", index=True, nullable=False)
    """操作类型（读/写）"""


class AppHashes(Base):
    """应用哈希"""

    __tablename__ = "framework_app_hashes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""
    appId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("framework_app.id"), nullable=False)  # noqa: N815
    """关联的应用ID"""
    filePath: Mapped[str] = mapped_column(String(255), nullable=False)  # noqa: N815
    """文件路径"""
    hash: Mapped[str] = mapped_column(String(255), nullable=False)
    """哈希值"""


class AppMCP(Base):
    """App使用MCP情况"""

    __tablename__ = "framework_app_mcp"

    appId: Mapped[uuid.UUID] = mapped_column(  # noqa: N815
        UUID(as_uuid=True),
        ForeignKey("framework_app.id"),
        primary_key=True,
        nullable=False,
    )
    """关联的应用ID"""

    mcpId: Mapped[str] = mapped_column(  # noqa: N815
        String(255),
        ForeignKey("framework_mcp.id"),
        primary_key=True,
        nullable=False,
    )
    """关联的MCP服务ID"""

    createdAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=UTC),
        nullable=False,
        index=True,
    )
    """创建时间"""
