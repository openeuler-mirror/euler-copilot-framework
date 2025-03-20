"""OIDC模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

import aiohttp
from fastapi import status

from apps.common.config import config
from apps.constants import LOGGER
from apps.models.redis import RedisConnectionPool


class OIDCProviderBase:
    """OIDC Provider Base"""

    @classmethod
    async def get_oidc_token(cls, code: str) -> dict[str, Any]:
        """获取OIDC Token"""
        raise NotImplementedError

    @classmethod
    async def get_oidc_user(cls, access_token: str) -> dict[str, Any]:
        """获取OIDC用户"""
        raise NotImplementedError

    @classmethod
    async def get_login_status(cls, token: str):
        """检查登录状态"""
        raise NotImplementedError

    @classmethod
    async def oidc_logout(cls, token: str):
        """触发OIDC的登出"""
        raise NotImplementedError



class OIDCProvider:
    """OIDC Provider"""

    def __init__(self):
        self.provider = provider

    async def set_redis_token(self, user_sub: str, access_token: str, refresh_token: str) -> None:
        """设置Redis中的OIDC Token"""
        async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
            pipe.set(f"{user_sub}_oidc_access_token", access_token, int(config["OIDC_ACCESS_TOKEN_EXPIRE_TIME"]) * 60)
            pipe.set(f"{user_sub}_oidc_refresh_token", refresh_token, int(config["OIDC_REFRESH_TOKEN_EXPIRE_TIME"]) * 60)
            await pipe.execute()

    async def get_login_status(self, token: str):
        """检查登录状态"""
        ...

    async def oidc_logout(self, token: str):
        """触发OIDC的登出"""
        ...


oidc_provider = OIDCProvider()
