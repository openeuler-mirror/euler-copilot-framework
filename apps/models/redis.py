# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import redis
import logging

from apps.common.config import config


class RedisConnectionPool:
    _redis_pool = None
    logger = logging.getLogger('gunicorn.error')

    @classmethod
    def get_redis_pool(cls):
        if not cls._redis_pool:
            cls._redis_pool = redis.ConnectionPool(
                host=config['REDIS_HOST'],
                port=config['REDIS_PORT'],
                password=config['REDIS_PWD']
            )
        return cls._redis_pool

    @classmethod
    def get_redis_connection(cls):
        try:
            pool = redis.Redis(connection_pool=cls.get_redis_pool())
        except Exception as e:
            cls.logger.error(f"Init redis connection failed: {e}")
            return None
        return cls._ConnectionManager(pool)

    class _ConnectionManager:
        def __init__(self, connection):
            self.connection = connection

        def __enter__(self):
            return self.connection

        def __exit__(self, exc_type, exc_val, exc_tb):
            try:
                self.connection.close()
            except Exception as e:
                RedisConnectionPool.logger.error(f"Redis connection close failed: {e}")
