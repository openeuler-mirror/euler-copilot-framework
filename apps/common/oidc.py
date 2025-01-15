"""OIDC模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

import aiohttp
from fastapi import status

from apps.common.config import config
from apps.constants import LOGGER
from apps.models.redis import RedisConnectionPool


async def get_oidc_token(code: str) -> dict[str, Any]:
    """获取OIDC Token"""
    if config["DEPLOY_MODE"] == "local":
        return await get_local_oidc_token(code)
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

async def set_redis_token(user_sub: str, access_token: str, refresh_token: str) -> None:
    """设置Redis中的OIDC Token"""
    async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
        pipe.set(f"{user_sub}_oidc_access_token", access_token, int(config["OIDC_ACCESS_TOKEN_EXPIRE_TIME"]) * 60)
        pipe.set(f"{user_sub}_oidc_refresh_token", refresh_token, int(config["OIDC_REFRESH_TOKEN_EXPIRE_TIME"]) * 60)
        await pipe.execute()


async def get_oidc_user(access_token: str, refresh_token: str) -> dict:
    """获取OIDC用户"""
    if config["DEPLOY_MODE"] == "local":
        return await get_local_oidc_user(access_token, refresh_token)

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

    user_sub = result["sub"]
    await set_redis_token(user_sub, access_token, refresh_token)

    return {
        "user_sub": user_sub,
    }


async def get_local_oidc_token(code: str) -> dict[str, Any]:
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
            err = f"Get OIDC token error: {resp.status}, full response is: {await resp.text()}"
            raise RuntimeError(err)
        LOGGER.info(f"full response is {await resp.text()}")
        result = await resp.json()
    return {
        "access_token": result["data"]["access_token"],
        "refresh_token": result["data"]["refresh_token"],
    }


async def get_local_oidc_user(access_token: str, refresh_token: str) -> dict:
    """获取本地OIDC用户"""
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
            err = f"Get OIDC user error: {resp.status}, full response is: {await resp.text()}"
            raise RuntimeError(err)
        LOGGER.info(f"full response is {await resp.text()}")
        result = await resp.json()
    user_sub = result["data"]
    await set_redis_token(user_sub, access_token, refresh_token)

    return {
        "user_sub": user_sub,
    }
