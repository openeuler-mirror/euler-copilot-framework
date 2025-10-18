# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Authelia OIDC Provider"""

import logging
import secrets
from typing import Any

import httpx
from fastapi import status

from apps.common.config import Config
from apps.common.oidc_provider.base import OIDCProviderBase
from apps.schemas.config import AutheliaConfig

logger = logging.getLogger(__name__)


class AutheliaOIDCProvider(OIDCProviderBase):
    """Authelia OIDC Provider"""

    @classmethod
    def _get_login_config(cls) -> AutheliaConfig:
        """获取并验证登录配置"""
        login_config = Config().get_config().login.settings
        if not isinstance(login_config, AutheliaConfig):
            err = "Authelia OIDC配置错误"
            raise TypeError(err)
        return login_config

    @classmethod
    async def get_oidc_token(cls, code: str) -> dict[str, Any]:
        """获取Authelia OIDC Token"""
        login_config = cls._get_login_config()

        data = {
            "client_id": login_config.client_id,
            "client_secret": login_config.client_secret,
            "redirect_uri": login_config.redirect_uri,
            "grant_type": "authorization_code",
            "code": code,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        url = await cls.get_access_token_url()
        result = None
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.post(
                url,
                headers=headers,
                data=data,
                timeout=10,
            )
            if resp.status_code != status.HTTP_200_OK:
                err = f"[Authelia] 获取OIDC Token失败: {resp.status_code}，完整输出: {resp.text}"
                raise RuntimeError(err)
            logger.info("[Authelia] 获取OIDC Token成功: %s", resp.text)
            result = resp.json()
        return {
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token", ""),
        }

    @classmethod
    async def get_oidc_user(cls, access_token: str) -> dict[str, Any]:
        """获取Authelia OIDC用户"""
        login_config = cls._get_login_config()

        if not access_token:
            err = "Access token is empty."
            raise RuntimeError(err)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        url = login_config.host.rstrip("/") + "/api/oidc/userinfo"
        result = None
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.get(
                url,
                headers=headers,
                timeout=10,
            )
            if resp.status_code != status.HTTP_200_OK:
                err = f"[Authelia] 获取用户信息失败: {resp.status_code}，完整输出: {resp.text}"
                raise RuntimeError(err)
            logger.info("[Authelia] 获取用户信息成功: %s", resp.text)
            result = resp.json()

        return {
            "user_sub": result.get("sub", result.get("preferred_username", "")),
            "user_name": result.get("name", result.get("preferred_username", result.get("nickname", ""))),
        }

    @classmethod
    async def get_login_status(cls, cookie: dict[str, str]) -> dict[str, Any]:
        """检查登录状态；Authelia通过session cookie检查"""
        login_config = cls._get_login_config()

        headers = {
            "Content-Type": "application/json",
        }
        url = login_config.host.rstrip("/") + "/api/user/info"
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.get(
                url,
                headers=headers,
                cookies=cookie,
                timeout=10,
            )
            if resp.status_code != status.HTTP_200_OK:
                err = f"[Authelia] 获取登录状态失败: {resp.status_code}，完整输出: {resp.text}"
                raise RuntimeError(err)
            result = resp.json()
            
            # Authelia 返回用户信息表示已登录，需要获取或生成token
            # 这里返回空的token，实际使用中可能需要根据具体情况调整
            return {
                "access_token": "",
                "refresh_token": "",
            }

    @classmethod
    async def oidc_logout(cls, cookie: dict[str, str]) -> None:
        """触发OIDC的登出"""
        login_config = cls._get_login_config()

        headers = {
            "Content-Type": "application/json",
        }
        url = login_config.host.rstrip("/") + "/api/logout"
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.post(
                url,
                headers=headers,
                cookies=cookie,
                timeout=10,
            )
            # Authelia登出成功通常返回200或302重定向
            if resp.status_code not in [status.HTTP_200_OK, status.HTTP_302_FOUND]:
                err = f"[Authelia] 登出失败: {resp.status_code}，完整输出: {resp.text}"
                raise RuntimeError(err)

    @classmethod
    async def get_redirect_url(cls) -> str:
        """获取Authelia OIDC 重定向URL"""
        login_config = cls._get_login_config()

        # 生成随机的 state 参数以确保安全性和唯一性
        state = secrets.token_urlsafe(32)
        return (f"{login_config.host.rstrip('/')}/api/oidc/authorization?"
                f"client_id={login_config.client_id}&"
                f"response_type=code&"
                f"scope=openid profile email&"
                f"redirect_uri={login_config.redirect_uri}&"
                f"state={state}")

    @classmethod
    async def get_access_token_url(cls) -> str:
        """获取Authelia OIDC 访问Token URL"""
        login_config = cls._get_login_config()
        return login_config.host.rstrip("/") + "/api/oidc/token"
