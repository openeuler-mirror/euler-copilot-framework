"""会话相关 数据库表"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SessionActivity(Base):
    """会话活动"""

    __tablename__ = "framework_session_activity"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""
    userId: Mapped[str] = mapped_column(String(50), ForeignKey("framework_user.id"), nullable=False)  # noqa: N815
    """用户ID"""
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    """时间戳"""
