"""Token Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Optional

import aiohttp
from fastapi import status

from apps.common.config import config
from apps.constants import LOGGER
from apps.manager.session import SessionManager
from apps.models.redis import RedisConnectionPool


class TokenManager:
    """管理用户Token和插件Token"""

    @staticmethod
    async def get_plugin_token(plugin_name: str, session_id: str, access_token_url: str, expire_time: int) -> str:
        """获取插件Token"""
        user_sub = await SessionManager.get_user(session_id=session_id)
        if not user_sub:
            err = "用户不存在！"
            raise ValueError(err)
        async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
            pipe.get(f"{user_sub}_token_{plugin_name}")
            result = await pipe.execute()
        if result[0] is not None:
            return result[0].decode()

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
    async def generate_plugin_token(
        plugin_name: str,
        session_id: str,
        user_sub: str,
        access_token_url: str,
        expire_time: int,
    ) -> Optional[str]:
        """生成插件Token"""
        async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
            pipe.get(f"{user_sub}_oidc_access_token")
            pipe.get(f"{user_sub}_oidc_refresh_token")
            result = await pipe.execute()
        if result[0]:
            oidc_access_token = result[0]
        elif result[1]:
            # access token 过期的时候，重新获取
            url = config["OIDC_REFRESH_TOKEN_URL"]
            async with aiohttp.ClientSession() as session:
                response = await session.post(
                    url=url,
                    json={
                        "refresh_token": result[1].decode(),
                        "client_id": config["OIDC_APP_ID"],
                    },
                )
                ret = await response.json()
                if response.status != status.HTTP_200_OK:
                    LOGGER.error(f"获取OIDC Access token 失败: {ret}")
                    return None
                oidc_access_token = ret["data"]["access_token"]
                pipe.set(f"{user_sub}_oidc_access_token", oidc_access_token, int(config["OIDC_ACCESS_TOKEN_EXPIRE_TIME"]) * 60)
                await pipe.execute()
        else:
            await SessionManager.delete_session(session_id)
            err = "Refresh token均过期，需要重新登录"
            raise RuntimeError(err)

        async with aiohttp.ClientSession() as session:
            response = await session.post(
                url=access_token_url,
                json={
                    "client_id": config["OIDC_APP_ID"],
                    "access_token": oidc_access_token.decode(),
                },
            )
            ret = await response.json()
            if response.status != status.HTTP_200_OK:
                LOGGER.error(f"获取{plugin_name}插件所需的token失败")
                return None
            async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
                pipe.set(f"{plugin_name}_{user_sub}_token", ret["data"]["access_token"], int(expire_time) * 60)
                await pipe.execute()
            return ret["data"]["access_token"]

    @staticmethod
    async def delete_plugin_token(user_sub: str) -> None:
        """删除插件token"""
        async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
            # 删除 oidc related token
            pipe.delete(f"{user_sub}_oidc_access_token")
            pipe.delete(f"{user_sub}_oidc_refresh_token")
            pipe.delete(f"aops_{user_sub}_token")
            await pipe.execute()

