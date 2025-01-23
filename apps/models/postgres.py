"""向postgresql中存储向量化数据

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from apps.common.config import config
from apps.entities.vector import Base


class PostgreSQL:
    """PostgreSQL向量化存储"""

    _engine = create_async_engine(
        f"postgresql+asyncpg://{config['POSTGRES_USER']}:{config['POSTGRES_PWD']}@{config['POSTGRES_HOST']}/{config['POSTGRES_DATABASE']}",
        echo=True,
        pool_recycle=300,
        pool_pre_ping=True,
    )
    _is_inited = False

    @classmethod
    async def init(cls) -> None:
        """初始化PostgreSQL"""
        if cls._is_inited:
            return
        cls._is_inited = True
        async with cls._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @classmethod
    async def get_session(cls) -> AsyncSession:
        """获取异步会话"""
        return async_sessionmaker(cls._engine, class_=AsyncSession, expire_on_commit=False)()
