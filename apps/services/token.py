# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Token Manager"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import status
from sqlalchemy import and_, select

from apps.common.config import config
from apps.common.oidc import oidc_provider
from apps.common.postgres import postgres
from apps.constants import OIDC_ACCESS_TOKEN_EXPIRE_TIME
from apps.models import Session, SessionType
from apps.schemas.config import OIDCConfig

logger = logging.getLogger(__name__)


class TokenManager:
    """管理用户Token和插件Token"""

    @staticmethod
    async def get_plugin_token(
        plugin_id: uuid.UUID,
        user_id: str,
        access_token_url: str,
        expire_time: int,
    ) -> str:
        """获取插件Token"""
        if not user_id:
            err = "用户不存在！"
            raise ValueError(err)

        async with postgres.session() as session:
            token_data = (
                await session.scalars(
                    select(Session)
                    .where(
                        and_(
                            Session.userId == user_id,
                            Session.sessionType == SessionType.ACCESS_TOKEN,
                            Session.pluginId == str(plugin_id),
                        ),
                    ),
                )
            ).one_or_none()

            if token_data and token_data.token:
                return token_data.token

            token = await TokenManager.generate_plugin_token(
                plugin_id,
                user_id,
                access_token_url,
                expire_time,
            )
            if token is None:
                err = "Generate plugin token failed"
                raise RuntimeError(err)

            await session.merge(Session(
                userId=user_id,
                sessionType=SessionType.PLUGIN_TOKEN,
                pluginId=str(plugin_id),
                token=token,
            ))
            await session.commit()
        return token


    @staticmethod
    def _get_login_config() -> OIDCConfig:
        """获取并验证登录配置"""
        login_config = config.login.settings
        if not isinstance(login_config, OIDCConfig):
            err = "Authhub OIDC配置错误"
            raise TypeError(err)
        return login_config


    @staticmethod
    async def generate_plugin_token(
        plugin_name: uuid.UUID,
        user_id: str,
        access_token_url: str,
        expire_time: int,
    ) -> str | None:
        """生成插件Token"""
        async with postgres.session() as session:
            token_data = (
                await session.scalars(
                    select(Session)
                    .where(
                        and_(
                            Session.userId == user_id,
                            Session.sessionType == SessionType.ACCESS_TOKEN,
                        ),
                    ),
                )
            ).one_or_none()

        if token_data:
            oidc_access_token = token_data.token
        else:
            # 检查是否有refresh token
            async with postgres.session() as session:
                refresh_token = (
                    await session.scalars(
                        select(Session)
                        .where(
                            and_(
                                Session.userId == user_id,
                                Session.sessionType == SessionType.REFRESH_TOKEN,
                            ),
                        ),
                    )
                ).one_or_none()

            if not refresh_token or not refresh_token.token:
                err = "Refresh token均过期，需要重新登录"
                raise RuntimeError(err)

            # access token 过期的时候，重新获取
            oidc_config = TokenManager._get_login_config()
            try:
                token_info = await oidc_provider.get_oidc_token(refresh_token.token)
                oidc_access_token = token_info["access_token"]

                # 更新OIDC token
                async with postgres.session() as session:
                    await session.merge(Session(
                        userId=user_id,
                        sessionType=SessionType.ACCESS_TOKEN,
                        token=oidc_access_token,
                        validUntil=datetime.now(UTC) + timedelta(minutes=OIDC_ACCESS_TOKEN_EXPIRE_TIME),
                    ))
                    await session.commit()
            except Exception:
                logger.exception("[TokenManager] 获取OIDC Access token 失败")
                return None

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=access_token_url,
                json={
                    "client_id": oidc_config.app_id,
                    "access_token": oidc_access_token,
                },
                timeout=10.0,
            )
            ret = response.json()
            if response.status_code != status.HTTP_200_OK:
                logger.error("[TokenManager] 获取 %s 插件所需的token失败", plugin_name)
                return None

            # 保存插件token
            async with postgres.session() as session:
                await session.merge(Session(
                    userId=user_id,
                    sessionType=SessionType.ACCESS_TOKEN,
                    pluginId=str(plugin_name),
                    token=ret["access_token"],
                    validUntil=datetime.now(UTC) + timedelta(minutes=expire_time),
                ))
                await session.commit()

            return ret["access_token"]


    @staticmethod
    async def delete_plugin_token(user_id: str) -> None:
        """删除插件token（使用PostgreSQL）"""
        async with postgres.session() as session:
            token_data = (await session.scalars(
                select(Session)
                .where(
                    and_(
                        Session.userId == user_id,
                        Session.sessionType.in_([
                            SessionType.ACCESS_TOKEN,
                            SessionType.REFRESH_TOKEN,
                            SessionType.PLUGIN_TOKEN,
                        ]),
                    ),
                ),
            )).all()
            for token in token_data:
                await session.delete(token)
            await session.commit()
