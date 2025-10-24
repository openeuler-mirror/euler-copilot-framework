# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Authhub OIDC Provider"""

import logging
from typing import Any

import httpx
from fastapi import status

from apps.common.config import config
from apps.schemas.config import OIDCConfig

from .base import OIDCProviderBase

logger = logging.getLogger(__name__)


class AuthhubOIDCProvider(OIDCProviderBase):
    """Authhub OIDC Provider"""

    @classmethod
    def _get_login_config(cls) -> OIDCConfig:
        """获取并验证登录配置"""
        login_config = config.login.settings
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
        headers = {
            "Content-Type": "application/json",
        }
        url = login_config.host_inner.rstrip("/") + "/oauth2/introspect"
        data = {
            "token": access_token,
            "client_id": login_config.app_id,
        }
        result = None
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=headers,
                json=data,
                timeout=10,
            )
            if resp.status_code != status.HTTP_200_OK:
                err = f"[Authhub] 获取用户信息失败: {resp.status_code}，完整输出: {resp.text}"
                raise RuntimeError(err)
            logger.info("[Authhub] 获取用户信息成功: %s", resp.text)
            result = resp.json()

        return {
            "user_sub": result["data"],
            "user_name": result["data"],
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
            if resp.status_code != status.HTTP_200_OK:
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

