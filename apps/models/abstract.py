import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.models.base import Base


class Abstract(Base):
    """记录摘要表（PG数据库适配版）"""

    __tablename__ = "framework_record_abstract"
    __table_args__ = (
        Index("idx_record_abstract_record_id", "recordId"),
    )  # type: ignore

    # 1. 主键ID（保留原有配置）
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default_factory=uuid.uuid4,
        comment="摘要记录ID"
    )

    # 2. 关联记录ID：核心修改→添加 default=None（显式默认值）
    recordId: Mapped[uuid.UUID | None] = mapped_column(  # noqa: N815
        PGUUID(as_uuid=True),
        nullable=True,
        default=None,  # ✅ 关键修复：添加显式默认值，解决dataclass顺序问题
        comment="关联的记录ID（对应Task.recordId）"
    )

    # 3. 摘要内容（保留原有配置）
    recordAbstract: Mapped[str] = mapped_column(  # noqa: N815
        String(2000),
        nullable=False,
        default="",
        comment="记录的摘要内容"
    )

    # 4. 创建时间（保留原有配置）
    createdAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=UTC),
        nullable=False,
        index=True,
        comment="摘要创建时间（UTC）"
    )

    # 5. 更新时间（保留原有配置）
    updatedAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=UTC),
        onupdate=lambda: datetime.now(tz=UTC),
        nullable=False,
        comment="摘要更新时间（UTC）"
    )

    def __repr__(self) -> str:  # noqa: D105
        return f"<Abstract(id={self.id}, recordId={self.recordId}, abstract_len={len(self.recordAbstract)})>"