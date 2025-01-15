"""用户限流

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from datetime import datetime, timezone

from apps.constants import SLIDE_WINDOW_QUESTION_COUNT, SLIDE_WINDOW_TIME
from apps.models.redis import RedisConnectionPool

_SLIDE_WINDOW_KEY = "slide_window"

class Activity:
    """用户活动控制，限制单用户同一时间只能提问一个问题"""

    @staticmethod
    async def is_active(user_sub: str) -> bool:
        """判断当前用户是否正在提问（占用GPU资源）

        :param user_sub: 用户实体ID
        :return: 判断结果，正在提问则返回True
        """
        time = round(datetime.now(timezone.utc).timestamp(), 3)
        async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
            # 检查窗口内总请求数
            pipe.zcount(_SLIDE_WINDOW_KEY, time - SLIDE_WINDOW_TIME, time)
            result = await pipe.execute()
            if result[0] >= SLIDE_WINDOW_QUESTION_COUNT:
                # 服务器处理请求过多
                return True

            # 检查用户是否正在提问
            pipe.get(f"{user_sub}_active")
            result = await pipe.execute()
            if result[0]:
                return True
        return False

    @staticmethod
    async def set_active(user_sub: str) -> None:
        """设置用户的活跃标识"""
        time = round(datetime.now(timezone.utc).timestamp(), 3)
        async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
            # 设置限流
            pipe.set(f"{user_sub}_active", 1)
            pipe.expire(f"{user_sub}_active", 300)
            pipe.zadd(_SLIDE_WINDOW_KEY, {f"{user_sub}_{time}": time})
            await pipe.execute()

    @staticmethod
    async def remove_active(user_sub: str) -> None:
        """清除用户的活跃标识，释放GPU资源

        :param user_sub: 用户实体ID
        """
        time = round(datetime.now(timezone.utc).timestamp(), 3)
        async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
            # 清除用户当前活动标识
            pipe.delete(f"{user_sub}_active")

            # 清除超出窗口范围的请求记录
            pipe.zremrangebyscore(_SLIDE_WINDOW_KEY, 0, time - SLIDE_WINDOW_TIME)
            await pipe.execute()
