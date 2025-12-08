# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""插件 数据库表"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .app import PermissionType
from .base import Base


class Service(Base):
    """插件"""

    __tablename__ = "framework_service"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """插件名称"""
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    """插件描述"""
    authorId: Mapped[str] = mapped_column(String(50), nullable=False)  # noqa: N815
    """插件作者ID"""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    """插件ID"""
    updatedAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=UTC),
        onupdate=lambda: datetime.now(tz=UTC),
        nullable=False,
    )
    """插件更新时间"""
    permission: Mapped[PermissionType] = mapped_column(
        Enum(PermissionType), default=PermissionType.PUBLIC, nullable=False,
    )
    """权限类型"""


class ServiceACL(Base):
    """插件权限"""

    __tablename__ = "framework_service_acl"
    serviceId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("framework_service.id"), nullable=False)  # noqa: N815
    """关联的插件ID"""
    userId: Mapped[str] = mapped_column(String(50), ForeignKey("framework_user.id"), nullable=False)  # noqa: N815
    """用户ID"""
    action: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    """操作类型（读/写）"""
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""


class ServiceHashes(Base):
    """插件哈希"""

    __tablename__ = "framework_service_hashes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""
    serviceId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("framework_service.id"), nullable=False)  # noqa: N815
    """关联的插件ID"""
    filePath: Mapped[str] = mapped_column(String(255), nullable=False)  # noqa: N815
    """文件路径"""
    hash: Mapped[str] = mapped_column(String(255), nullable=False)
    """哈希值"""
