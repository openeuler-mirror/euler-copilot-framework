"""OIDC模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

from apps.common.config import config
from apps.common.oidc_provider.authhub import AuthhubOIDCProvider
from apps.common.oidc_provider.openeuler import OpenEulerOIDCProvider
from apps.constants import LOGGER
from apps.models.redis import RedisConnectionPool


class OIDCProvider:
    """OIDC Provider"""

    def __init__(self) -> None:
        """初始化OIDC Provider"""
        if config["OIDC_PROVIDER"] == "openeuler":
            self.provider = OpenEulerOIDCProvider()
        elif config["OIDC_PROVIDER"] == "authhub":
            self.provider = AuthhubOIDCProvider()
        else:
            err = f"[OIDC] 未知OIDC提供商: {config['OIDC_PROVIDER']}"
            LOGGER.error(err)
            raise NotImplementedError(err)

    @staticmethod
    async def set_redis_token(user_sub: str, access_token: str, refresh_token: str) -> None:
        """设置Redis中的OIDC Token"""
        async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
            pipe.set(f"{user_sub}_oidc_access_token", access_token, int(config["OIDC_ACCESS_TOKEN_EXPIRE_TIME"]) * 60)
            pipe.set(f"{user_sub}_oidc_refresh_token", refresh_token, int(config["OIDC_REFRESH_TOKEN_EXPIRE_TIME"]) * 60)
            await pipe.execute()


    async def get_login_status(self, cookie: dict[str, str]) -> dict[str, Any]:
        """检查登录状态"""
        return await self.provider.get_login_status(cookie)


    async def oidc_logout(self, cookie: dict[str, str]) -> None:
        """触发OIDC的登出"""
        return await self.provider.oidc_logout(cookie)


    async def get_oidc_token(self, code: str) -> dict[str, Any]:
        """获取OIDC 访问Token"""
        return await self.provider.get_oidc_token(code)


    async def get_oidc_user(self, access_token: str) -> dict[str, Any]:
        """获取OIDC 用户信息"""
        return await self.provider.get_oidc_user(access_token)


oidc_provider = OIDCProvider()
