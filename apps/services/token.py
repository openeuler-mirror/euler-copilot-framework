# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Token Manager"""

import logging
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import status

from apps.common.config import Config
from apps.common.mongo import MongoDB
from apps.common.oidc import oidc_provider
from apps.constants import OIDC_ACCESS_TOKEN_EXPIRE_TIME
from apps.schemas.config import OIDCConfig
from apps.services.session import SessionManager

logger = logging.getLogger(__name__)


class TokenManager:
    """管理用户Token和插件Token"""

    @staticmethod
    async def get_plugin_token(plugin_name: str, session_id: str, access_token_url: str, expire_time: int) -> str:
        """获取插件Token"""
        user_sub = await SessionManager.get_user(session_id=session_id)
        if not user_sub:
            err = "用户不存在！"
            raise ValueError(err)

        collection = MongoDB.get_collection("session")
        token_data = await collection.find_one({
            "_id": f"{plugin_name}_token_{user_sub}",
        })

        if token_data:
            return token_data["token"]

        token = await TokenManager.generate_plugin_token(
            plugin_name,
            session_id,
            user_sub,
            access_token_url,
            expire_time,
        )
        if token is None:
            err = "Generate plugin token failed"
            raise RuntimeError(err)
        return token

    @staticmethod
    def _get_login_config() -> OIDCConfig:
        """获取并验证登录配置"""
        login_config = Config().get_config().login.settings
        if not isinstance(login_config, OIDCConfig):
            err = "Authhub OIDC配置错误"
            raise TypeError(err)
        return login_config

    @staticmethod
    async def generate_plugin_token(
        plugin_name: str,
        session_id: str,
        user_sub: str,
        access_token_url: str,
        expire_time: int,
    ) -> str | None:
        """生成插件Token"""
        collection = MongoDB.get_collection("session")

        # 获取OIDC token
        oidc_token = await collection.find_one({
            "_id": f"access_token_{user_sub}",
        })

        if oidc_token:
            oidc_access_token = oidc_token["token"]
        else:
            # 检查是否有refresh token
            refresh_token = await collection.find_one({
                "_id": f"refresh_token_{user_sub}",
            })

            if refresh_token:
                # access token 过期的时候，重新获取
                oidc_config = TokenManager._get_login_config()
                try:
                    token_info = await oidc_provider.get_oidc_token(refresh_token["token_value"])
                    oidc_access_token = token_info["access_token"]

                    # 更新OIDC token
                    await collection.update_one(
                        {"_id": f"access_token_{user_sub}"},
                        {"$set": {
                            "token": oidc_access_token,
                            "expired_at": datetime.now(UTC) + timedelta(minutes=OIDC_ACCESS_TOKEN_EXPIRE_TIME),
                        }},
                        upsert=True,
                    )
                    await collection.create_index("expired_at", expireAfterSeconds=0)
                except Exception:
                    logger.exception("[TokenManager] 获取OIDC Access token 失败")
                    return None
            else:
                await SessionManager.delete_session(session_id)
                err = "Refresh token均过期，需要重新登录"
                raise RuntimeError(err)

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
            await collection.update_one(
                {
                    "_id": f"{plugin_name}_token_{user_sub}",
                },
                {"$set": {
                    "token": ret["access_token"],
                    "expired_at": datetime.now(UTC) + timedelta(minutes=expire_time),
                }},
                upsert=True,
            )

            # 创建TTL索引
            await collection.create_index("expired_at", expireAfterSeconds=0)
            return ret["access_token"]

    @staticmethod
    async def delete_plugin_token(user_sub: str) -> None:
        """删除插件token"""
        collection = MongoDB.get_collection("token")
        await collection.delete_many({
            "user_sub": user_sub,
            "$or": [
                {"token_type": "oidc"},
                {"token_type": "oidc_refresh"},
                {"token_type": "plugin"},
            ],
        })
