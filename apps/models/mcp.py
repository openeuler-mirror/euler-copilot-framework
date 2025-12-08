# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 相关 数据库表"""

from datetime import UTC, datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MCPInstallStatus(str, PyEnum):
    """MCP 服务状态"""

    INIT = "init"
    INSTALLING = "installing"
    CANCELLED = "cancelled"
    READY = "ready"
    FAILED = "failed"


class MCPType(str, PyEnum):
    """MCP 类型"""

    SSE = "sse"
    STDIO = "stdio"
    STREAMABLE = "stream"


class MCPInfo(Base):
    """MCP"""

    __tablename__ = "framework_mcp"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """MCP 名称"""
    overview: Mapped[str] = mapped_column(String(2000), nullable=False)
    """MCP 概述"""
    description: Mapped[str] = mapped_column(Text, nullable=False)
    """MCP 描述"""
    authorId: Mapped[str] = mapped_column(String(50), nullable=False)  # noqa: N815
    """MCP 创建者ID"""
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    """MCP ID"""
    updatedAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=UTC),
        onupdate=lambda: datetime.now(tz=UTC),
        nullable=False,
        index=True,
    )
    """MCP 更新时间"""
    status: Mapped[MCPInstallStatus] = mapped_column(
        Enum(MCPInstallStatus), default=MCPInstallStatus.INIT, nullable=False,
    )
    """MCP 状态"""
    mcpType: Mapped[MCPType] = mapped_column(  # noqa: N815
        Enum(MCPType), default=MCPType.STDIO, nullable=False,
    )
    """MCP 类型"""


class MCPActivated(Base):
    """MCP 激活用户"""

    __tablename__ = "framework_mcp_activated"
    mcpId: Mapped[str] = mapped_column(  # noqa: N815
        String(255), ForeignKey("framework_mcp.id"), index=True, nullable=False,
    )
    """MCP ID"""
    userId: Mapped[str] = mapped_column(String(50), ForeignKey("framework_user.id"), nullable=False)  # noqa: N815
    """用户ID"""
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""


class MCPTools(Base):
    """MCP 工具"""

    __tablename__ = "framework_mcp_tools"
    mcpId: Mapped[str] = mapped_column(  # noqa: N815
        String(255), ForeignKey("framework_mcp.id"), index=True, nullable=False,
    )
    """MCP ID"""
    toolName: Mapped[str] = mapped_column(String(255), nullable=False)  # noqa: N815
    """MCP 工具名称"""
    description: Mapped[str] = mapped_column(Text, nullable=False)
    """MCP 工具描述"""
    inputSchema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # noqa: N815
    """MCP 工具输入参数"""
    outputSchema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # noqa: N815
    """MCP 工具输出参数"""
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        init=False,
    )
    """主键ID"""
