# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from __future__ import annotations

import requests
import logging

from apps.manager.session import SessionManager
from apps.models.redis import RedisConnectionPool
from apps.common.config import config

logger = logging.getLogger('gunicorn.error')


class PluginTokenManager:

    @staticmethod
    def get_plugin_token(plugin_domain, session_id, access_token_url, expire_time):
        user_sub = SessionManager.get_user(session_id=session_id).user_sub
        with RedisConnectionPool.get_redis_connection() as r:
            token = r.get(f'{plugin_domain}_{user_sub}_token')
        if not token:
            token = PluginTokenManager.generate_plugin_token(
                plugin_domain,
                session_id,
                user_sub,
                access_token_url,
                expire_time
                )
        if isinstance(token, str):
            return token
        else:
            return token.decode()


    @staticmethod
    def generate_plugin_token(
        plugin_domain, session_id: str, 
        user_sub: str, 
        access_token_url: str, 
        expire_time: int
    ):
        with RedisConnectionPool.get_redis_connection() as r:
            oidc_access_token = r.get(f'{user_sub}_oidc_access_token')
            oidc_refresh_token = r.get(f'{user_sub}_oidc_refresh_token')
        if not oidc_refresh_token:
            # refresh token均过期的情况下，需要重新登录
            SessionManager.delete_session(session_id)
        elif not oidc_access_token:
            # access token 过期的时候，重新获取
            url = config['OIDC_REFRESH_TOKEN_URL']
            response = requests.post(
                url=url,
                json={
                    "refresh_token": oidc_refresh_token.decode(),
                    "client_id": config["OIDC_APP_ID"]
                }
            )
            ret = response.json()
            if response.status_code != 200:
                logger.error('获取OIDC Access token 失败')
                return None
            oidc_access_token = ret['data']['access_token'],
            with RedisConnectionPool.get_redis_connection() as r:
                r.set(
                    f'{user_sub}_oidc_access_token', 
                    oidc_access_token,
                    int(config['OIDC_ACCESS_TOKEN_EXPIRE_TIME']) * 60
                )
        response = requests.post(
            url=access_token_url,
            json={
                "client_id": config['OIDC_APP_ID'],
                "access_token": oidc_access_token.decode()
            }
        )
        ret = response.json()
        if response.status_code != 200:
            logger.error(f'获取{plugin_domain} token失败')
            return None
        with RedisConnectionPool.get_redis_connection() as r:
            r.set(f'{plugin_domain}_{user_sub}_token', ret['data']['access_token'], int(expire_time)*60)
        return ret['data']['access_token']

