"""Redis连接池模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from __future__ import annotations

from redis import asyncio as aioredis

from apps.common.config import config
from apps.constants import LOGGER


class RedisConnectionPool:
    """Redis连接池"""

    _redis_pool = aioredis.ConnectionPool(
        host=config["REDIS_HOST"],
        port=config["REDIS_PORT"],
        password=config["REDIS_PWD"],
    )

    @classmethod
    def get_redis_connection(cls) -> aioredis.Redis:
        """从连接池中获取Redis连接"""
        try:
            return aioredis.Redis.from_pool(cls._redis_pool)
        except Exception as e:
            LOGGER.error(f"Init redis connection failed: {e}")
            msg = f"Init redis connection failed: {e}"
            raise RuntimeError(msg) from e
