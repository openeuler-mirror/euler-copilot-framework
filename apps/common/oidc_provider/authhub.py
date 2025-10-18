# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Authhub OIDC Provider"""

import logging
from typing import Any

import httpx
from fastapi import status

from apps.common.config import Config
from apps.common.oidc_provider.base import OIDCProviderBase
from apps.schemas.config import OIDCConfig

logger = logging.getLogger(__name__)


class AuthhubOIDCProvider(OIDCProviderBase):
    """Authhub OIDC Provider"""

    @classmethod
    def _get_login_config(cls) -> OIDCConfig:
        """获取并验证登录配置"""
        login_config = Config().get_config().login.settings
        if not isinstance(login_config, OIDCConfig):
            err = "Authhub OIDC配置错误"
            raise TypeError(err)
        return login_config

    @classmethod
    async def get_oidc_token(cls, code: str) -> dict[str, Any]:
        """获取AuthHub OIDC Token"""
        login_config = cls._get_login_config()

        data = {
            "client_id": login_config.app_id,
            "redirect_uri": login_config.login_api,
            "grant_type": "authorization_code",
            "code": code,
        }
        headers = {
            "Content-Type": "application/json",
        }
        url = await cls.get_access_token_url()
        result = None
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=headers,
                json=data,
                timeout=10,
            )
            if resp.status_code != status.HTTP_200_OK:
                err = f"[Authhub] 获取OIDC Token失败: {resp.status_code}，完整输出: {resp.text}"
                raise RuntimeError(err)
            logger.info("[Authhub] 获取OIDC Token成功: %s", resp.text)
            result = resp.json()
        return {
            "access_token": result["data"]["access_token"],
            "refresh_token": result["data"]["refresh_token"],
        }

    @classmethod
    async def get_oidc_user(cls, access_token: str) -> dict[str, Any]:
        """获取Authhub OIDC用户"""
        login_config = cls._get_login_config()

        if not access_token:
            err = "Access token is empty."
            raise RuntimeError(err)
        # 首先尝试使用标准的 userinfo 端点
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        userinfo_url = login_config.host_inner.rstrip("/") + "/oauth2/userinfo"
        
        result = None
        async with httpx.AsyncClient() as client:
            # 尝试 userinfo 端点
            resp = await client.get(
                userinfo_url,
                headers=headers,
                timeout=10,
            )
            
            if resp.status_code == status.HTTP_200_OK:
                logger.info("[Authhub] 从 userinfo 端点获取用户信息成功: %s", resp.text)
                result = resp.json()
            else:
                # 如果 userinfo 端点失败，回退到 introspect 端点
                logger.warning("[Authhub] userinfo 端点失败，尝试 introspect 端点")
                introspect_url = login_config.host_inner.rstrip("/") + "/oauth2/introspect"
                data = {
                    "token": access_token,
                    "client_id": login_config.app_id,
                }
                headers = {
                    "Content-Type": "application/json",
                }
                resp = await client.post(
                    introspect_url,
                    headers=headers,
                    json=data,
                    timeout=10,
                )
            if resp.status_code != status.HTTP_200_OK:
                err = f"[Authhub] 获取用户信息失败: {resp.status_code}，完整输出: {resp.text}"
                raise RuntimeError(err)
            logger.info("[Authhub] 获取用户信息成功: %s", resp.text)
            result = resp.json()

        # 记录完整的响应结构用于调试
        logger.info("[Authhub] 完整响应结构: %s", result)
        
        # 根据不同的端点响应结构提取用户信息
        if "sub" in result:
            # 标准 OIDC userinfo 响应
            user_sub = result["sub"]
            user_name = result.get("name", result.get("preferred_username", result.get("nickname", result.get("username", ""))))
        elif "data" in result:
            # Authhub introspect 响应
            user_data = result["data"]
            if isinstance(user_data, str):
                # 如果data是字符串，说明只返回了user_sub
                user_sub = user_data
                user_name = ""
            else:
                # 如果data是对象，尝试提取用户信息
                user_sub = user_data.get("sub", user_data.get("user_id", str(user_data)))
                user_name = user_data.get("name", user_data.get("preferred_username", user_data.get("nickname", user_data.get("username", ""))))
        else:
            # 其他格式，尝试直接提取
            user_sub = result.get("sub", result.get("user_id", ""))
            user_name = result.get("name", result.get("preferred_username", result.get("nickname", result.get("username", ""))))

        logger.info("[Authhub] 提取的用户信息 - user_sub: %s, user_name: %s", user_sub, user_name)
        
        return {
            "user_sub": user_sub,
            "user_name": user_name,
        }

    @classmethod
    async def get_login_status(cls, cookie: dict[str, str]) -> dict[str, Any]:
        """检查登录状态；Authhub的Token实际是cookie"""
        login_config = cls._get_login_config()

        data = {
            "client_id": login_config.app_id,
        }
        headers = {
            "Content-Type": "application/json",
        }
        url = login_config.host_inner.rstrip("/") + "/oauth2/login-status"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=headers,
                json=data,
                cookies=cookie,
                timeout=10,
            )
            if resp.status_code != status.HTTP_200_OK:
                err = f"[Authhub] 获取登录状态失败: {resp.status_code}，完整输出: {resp.text}"
                raise RuntimeError(err)
            result = resp.json()
            return {
                "access_token": result["data"]["access_token"],
                "refresh_token": result["data"]["refresh_token"],
            }

    @classmethod
    async def oidc_logout(cls, cookie: dict[str, str]) -> None:
        """触发OIDC的登出"""
        login_config = cls._get_login_config()

        headers = {
            "Content-Type": "application/json",
        }
        url = login_config.host_inner.rstrip("/") + "/oauth2/logout"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=headers,
                cookies=cookie,
                timeout=10,
            )
            # authHub登出成功会返回302重定向，这是正常的
            if resp.status_code not in [status.HTTP_200_OK, status.HTTP_302_FOUND]:
                err = f"[Authhub] 登出失败: {resp.status_code}，完整输出: {resp.text}"
                raise RuntimeError(err)

    @classmethod
    async def get_redirect_url(cls) -> str:
        """获取Authhub OIDC 重定向URL"""
        login_config = cls._get_login_config()

        return (f"{login_config.host.rstrip('/')}/oauth2/authorize?client_id={login_config.app_id}"
                f"&response_type=code&access_type=offline&redirect_uri={login_config.login_api}"
                "&scope=openid offline_access&prompt=consent&nonce=loser")

    @classmethod
    async def get_access_token_url(cls) -> str:
        """获取Authhub OIDC 访问Token URL"""
        login_config = cls._get_login_config()
        return login_config.host_inner.rstrip("/") + "/oauth2/token"

