# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from apps.models.redis import RedisConnectionPool

class Activity:
    """
    用户活动控制，限制单用户同一时间只能提问一个问题
    """
    def __init__(self):
        raise NotImplementedError("Activity无法被实例化！")

    @staticmethod
    def is_active(user_sub) -> bool:
        """
        判断当前用户是否正在提问（占用GPU资源）
        :param user_sub: 用户实体ID
        :return: 判断结果，正在提问则返回True
        """
        with RedisConnectionPool.get_redis_connection() as r:
            if not r.get(f'{user_sub}_active'):
                return False
            else:
                r.expire(f'{user_sub}_active', 300)
        return True

    @staticmethod
    def remove_active(user_sub):
        """
        清除用户的活动标识，释放GPU资源
        :param user_sub: 用户实体ID
        :return:
        """
        with RedisConnectionPool.get_redis_connection() as r:
            r.delete(f'{user_sub}_active')
