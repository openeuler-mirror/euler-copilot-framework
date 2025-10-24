# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""全局设置 数据库表"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class GlobalSettings(Base):
    """全局设置"""

    __tablename__ = "framework_global_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    """设置ID"""

    functionLlmId: Mapped[str | None] = mapped_column(  # noqa: N815
        String(255), ForeignKey("framework_llm.id"), nullable=True, default=None,
    )
    """Function Call使用的大模型ID"""

    embeddingLlmId: Mapped[str | None] = mapped_column(  # noqa: N815
        String(255), ForeignKey("framework_llm.id"), nullable=True, default=None,
    )
    """Embedding使用的大模型ID"""

    updatedAt: Mapped[DateTime] = mapped_column(  # noqa: N815
        DateTime,
        default_factory=lambda: datetime.now(tz=UTC),
        onupdate=lambda: datetime.now(tz=UTC),
        nullable=False,
    )
    """设置更新时间"""

    lastEditedBy: Mapped[str | None] = mapped_column(  # noqa: N815
        String(50), ForeignKey("framework_user.id"), nullable=True, default=None,
    )
    """最后一次修改的用户sub"""
