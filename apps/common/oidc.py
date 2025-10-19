# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""OIDC模块"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from apps.common.config import Config
from apps.common.mongo import MongoDB
from apps.common.oidc_provider.authhub import AuthhubOIDCProvider
from apps.common.oidc_provider.authelia import AutheliaOIDCProvider
from apps.common.oidc_provider.openeuler import OpenEulerOIDCProvider
from apps.constants import OIDC_ACCESS_TOKEN_EXPIRE_TIME, OIDC_REFRESH_TOKEN_EXPIRE_TIME

logger = logging.getLogger(__name__)


class OIDCProvider:
    """OIDC Provider"""

    def __init__(self) -> None:
        """初始化OIDC Provider"""
        if Config().get_config().login.provider == "openeuler":
            self.provider = OpenEulerOIDCProvider()
        elif Config().get_config().login.provider == "authhub":
            self.provider = AuthhubOIDCProvider()
        elif Config().get_config().login.provider == "authelia":
            self.provider = AutheliaOIDCProvider()
        else:
            err = f"[OIDC] 未知OIDC提供商: {Config().get_config().login.provider}"
            logger.error(err)
            raise NotImplementedError(err)

    @staticmethod
    async def set_token(user_sub: str, access_token: str, refresh_token: str) -> None:
        """设置MongoDB中的OIDC Token到sessions集合"""
        mongo = MongoDB()
        sessions_collection = mongo.get_collection("session")

        await sessions_collection.update_one(
            {"_id": f"access_token_{user_sub}"},
            {
                "$set": {
                    "token": access_token,
                    "expired_at": datetime.now(UTC) + timedelta(minutes=OIDC_ACCESS_TOKEN_EXPIRE_TIME),
                },
            },
            upsert=True,
        )
        await sessions_collection.update_one(
            {"_id": f"refresh_token_{user_sub}"},
            {
                "$set": {
                    "token": refresh_token,
                    "expired_at": datetime.now(UTC) + timedelta(minutes=OIDC_REFRESH_TOKEN_EXPIRE_TIME),
                },
            },
            upsert=True,
        )

        await sessions_collection.create_index(
            "expired_at",
            expireAfterSeconds=0,
        )

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

    async def get_redirect_url(self) -> str:
        """获取OIDC 重定向URL"""
        return await self.provider.get_redirect_url()

    async def get_access_token_url(self) -> str:
        """获取OIDC 访问Token URL"""
        return await self.provider.get_access_token_url()


oidc_provider = OIDCProvider()
