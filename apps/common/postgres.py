# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Postgres连接器"""

import logging
import urllib.parse
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from apps.models import Base

from .config import config

logger = logging.getLogger(__name__)


class Postgres:
    """Postgres连接器"""

    engine: AsyncEngine

    async def init(self) -> None:
        """初始化Postgres连接器"""
        logger.info("[Postgres] 初始化Postgres连接器")
        self.engine = create_async_engine(
            f"postgresql+asyncpg://{urllib.parse.quote_plus(config.postgres.user)}:"
            f"{urllib.parse.quote_plus(config.postgres.password)}@{config.postgres.host}:"
            f"{config.postgres.port}/{config.postgres.database}",
            pool_size=20,  # 连接池大小
            max_overflow=10,  # 允许的最大溢出连接数
            pool_pre_ping=True,  # 使用前检查连接是否有效
            pool_recycle=3600,  # 连接回收时间(秒)
            echo_pool=False,  # 是否打印连接池日志
        )

        logger.info("[Postgres] 创建表")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        """关闭Postgres连接器,释放所有连接"""
        logger.info("[Postgres] 关闭Postgres连接器")
        await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        获取会话,每次从连接池创建新的数据库连接

        注意: 此方法不会自动提交,调用方需要显式调用 session.commit()
        """
        # 每次调用都直接从 engine 创建新的 session
        session = AsyncSession(
            self.engine,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        try:
            yield session
        except Exception:
            logger.exception("[Postgres] 会话错误")
            # 发生异常时回滚
            await session.rollback()
            raise
        finally:
            # 确保连接被正确关闭并归还到连接池
            await session.close()

postgres = Postgres()
