"""Authhub OIDC Provider"""

from typing import Any

import aiohttp
from fastapi import status

from apps.common.config import config
from apps.common.oidc_provider.base import OIDCProviderBase
from apps.constants import LOGGER


class AuthhubOIDCProvider(OIDCProviderBase):
    """Authhub OIDC Provider"""

    @classmethod
    async def get_oidc_token(cls, code: str) -> dict[str, Any]:
        """获取AuthHub OIDC Token"""
        data = {
            "client_id": config["OIDC_APP_ID"],
            "redirect_uri": config["EULER_LOGIN_API"],
            "grant_type": "authorization_code",
            "code": code,
        }
        headers = {
            "Content-Type": "application/json",
        }
        url = config["OIDC_TOKEN_URL"]
        result = None
        async with aiohttp.ClientSession() as session, session.post(url, headers=headers, json=data, timeout=10) as resp:
            if resp.status != status.HTTP_200_OK:
                err = f"[Authhub] 获取OIDC Token失败: {resp.status}，完整输出: {await resp.text()}"
                raise RuntimeError(err)
            LOGGER.info(f"[Authhub] 获取OIDC Token成功: {await resp.text()}")
            result = await resp.json()
        return {
            "access_token": result["data"]["access_token"],
            "refresh_token": result["data"]["refresh_token"],
        }


    @classmethod
    async def get_oidc_user(cls, access_token: str) -> dict[str, Any]:
        """获取Authhub OIDC用户"""
        if not access_token:
            err = "Access token is empty."
            raise RuntimeError(err)
        headers = {
            "Content-Type": "application/json",
        }
        url = config["OIDC_USER_URL"]
        data = {
            "token": access_token,
            "client_id": config["OIDC_APP_ID"],
        }
        result = None
        async with aiohttp.ClientSession() as session, session.post(url, headers=headers, json=data, timeout=10) as resp:
            if resp.status != status.HTTP_200_OK:
                err = f"[Authhub] 获取用户信息失败: {resp.status}，完整输出: {await resp.text()}"
                raise RuntimeError(err)
            LOGGER.info(f"[Authhub] 获取用户信息成功: {await resp.text()}")
            result = await resp.json()

        return {
            "user_sub": result["data"],
        }


    @classmethod
    async def get_login_status(cls, cookie: dict[str, str]) -> dict[str, Any]:
        """检查登录状态；Authhub的Token实际是cookie"""
        data = {
            "client_id": config["OIDC_APP_ID"],
        }
        headers = {
            "Content-Type": "application/json",
        }
        url = config["OIDC_STATUS_URL"]
        async with aiohttp.ClientSession() as session, session.post(url, headers=headers, json=data, cookies=cookie, timeout=10) as resp:
            if resp.status != status.HTTP_200_OK:
                err = f"[Authhub] 获取登录状态失败: {resp.status}，完整输出: {await resp.text()}"
                raise RuntimeError(err)
            result = await resp.json()
            return {
                "access_token": result["access_token"],
                "refresh_token": result["refresh_token"],
            }


    @classmethod
    async def oidc_logout(cls, cookie: dict[str, str]) -> None:
        """触发OIDC的登出"""
        headers = {
            "Content-Type": "application/json",
        }
        url = config["OIDC_LOGOUT_URL"]
        async with aiohttp.ClientSession() as session, session.get(url, headers=headers, cookies=cookie, timeout=10) as resp:
            if resp.status != status.HTTP_200_OK:
                err = f"[Authhub] 登出失败: {resp.status}，完整输出: {await resp.text()}"
                raise RuntimeError(err)
