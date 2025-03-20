"""OpenEuler OIDC Provider"""

from typing import Any

import aiohttp
from fastapi import status

from apps.common.config import config
from apps.common.oidc import OIDCProviderBase
from apps.constants import LOGGER


class OpenEulerOIDCProvider(OIDCProviderBase):
    """OpenEuler OIDC Provider"""

    @classmethod
    async def get_oidc_token(cls, code: str) -> dict[str, Any]:
        """获取OIDC Token"""
        data = {
            "client_id": config["OIDC_APP_ID"],
            "client_secret": config["OIDC_APP_SECRET"],
            "redirect_uri": config["EULER_LOGIN_API"],
            "grant_type": "authorization_code",
            "code": code,
        }
        url = config["OIDC_TOKEN_URL"]
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        result = None
        async with aiohttp.ClientSession() as session, session.post(url, headers=headers, data=data, timeout=10) as resp:
            if resp.status != status.HTTP_200_OK:
                err = f"Get OIDC token error: {resp.status}, full output is: {await resp.text()}"
                raise RuntimeError(err)
            LOGGER.info(f"full response is {await resp.text()}")
            result = await resp.json()
        return {
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
        }


    @classmethod
    async def get_oidc_user(cls, access_token: str) -> dict:
        """获取OIDC用户"""
        if not access_token:
            err = "Access token is empty."
            raise RuntimeError(err)
        url = config["OIDC_USER_URL"]
        headers = {
            "Authorization": access_token,
        }

        result = None
        async with aiohttp.ClientSession() as session, session.get(url, headers=headers, timeout=10) as resp:
            if resp.status != status.HTTP_200_OK:
                err = f"Get OIDC user error: {resp.status}, full response is: {await resp.text()}"
                raise RuntimeError(err)
            LOGGER.info(f"full response is {await resp.text()}")
            result = await resp.json()

        if not result["phone_number_verified"]:
            err = "Could not validate credentials."
            raise RuntimeError(err)

        return {
            "user_sub": result["sub"],
        }

    @classmethod
    async def get_login_status(cls, token: str):
        """检查登录状态"""
        ...

    @classmethod
    async def oidc_logout(cls, token: str):
        """触发OIDC的登出"""
        ...
