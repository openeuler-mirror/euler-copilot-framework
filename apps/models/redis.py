"""Redis连接池模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import logging

from redis import asyncio as aioredis

from apps.common.config import config

logger = logging.getLogger("ray")


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
            error_msg = "[RedisConnectionPool] 初始化Redis连接失败"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
