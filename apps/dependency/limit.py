# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from limits import storage, strategies, RateLimitItemPerMinute
from functools import wraps

from apps.models.redis import RedisConnectionPool

from fastapi import Response


class Limit:
    memory_storage = storage.MemoryStorage()
    moving_window = strategies.MovingWindowRateLimiter(memory_storage)
    limit_rate = RateLimitItemPerMinute(50)


def moving_window_limit(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        user_sub = kwargs.get('user').user_sub
        rate_limit_response = Response(content='Rate limit exceeded', status_code=429)
        with RedisConnectionPool.get_redis_connection() as r:
            if r.get(f'{user_sub}_active'):
                return rate_limit_response
            if not Limit.moving_window.hit(Limit.limit_rate, "stream_answer", cost=1):
                return rate_limit_response
            r.setex(f'{user_sub}_active', 300, user_sub)
        return await func(*args, **kwargs)

    return wrapper
