# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""OIDC模块"""

import grp
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from apps.common.postgres import postgres
from apps.constants import OIDC_ACCESS_TOKEN_EXPIRE_TIME, OIDC_REFRESH_TOKEN_EXPIRE_TIME
from apps.models import Session, SessionType

from .config import config
from .oidc_provider import AuthhubOIDCProvider

logger = logging.getLogger(__name__)


class OIDCProvider:
    """OIDC Provider"""

    def __init__(self) -> None:
        """初始化OIDC Provider"""
        if config.login.provider == "authhub":
            self.provider = AuthhubOIDCProvider()
        else:
            err = f"[OIDC] 未知OIDC提供商: {config.login.provider}"
            logger.error(err)
            raise NotImplementedError(err)

    @staticmethod
    async def set_token(user_id: str, access_token: str, refresh_token: str) -> None:
        """设置MongoDB中的OIDC Token到sessions集合"""
        async with postgres.session() as session:
            await session.merge(Session(
                userId=user_id,
                sessionType=SessionType.ACCESS_TOKEN,
                token=access_token,
                validUntil=datetime.now(UTC) + timedelta(minutes=OIDC_ACCESS_TOKEN_EXPIRE_TIME),
            ))
            await session.merge(Session(
                userId=user_id,
                sessionType=SessionType.REFRESH_TOKEN,
                token=refresh_token,
                validUntil=datetime.now(UTC) + timedelta(minutes=OIDC_REFRESH_TOKEN_EXPIRE_TIME),
            ))
            await session.commit()

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
