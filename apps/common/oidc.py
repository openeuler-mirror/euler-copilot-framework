# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from __future__ import annotations

from typing import Dict, Any

import aiohttp
import logging 


from apps.common.config import config
from apps.models.redis import RedisConnectionPool
from apps.manager.gitee_white_list import GiteeIDManager

from fastapi import status, HTTPException

logger = logging.getLogger('gunicorn.error')


async def get_oidc_token(code: str) -> Dict[str, Any]:
    if config["DEPLOY_MODE"] == 'local':
        ret =  await get_local_oidc_token(code)
        return ret
    data = {
        "client_id": config["OIDC_APP_ID"],
        "client_secret": config["OIDC_APP_SECRET"],
        "redirect_uri": config["EULER_LOGIN_API"],
        "grant_type": "authorization_code",
        "code": code
    }
    url = config['OIDC_TOKEN_URL']
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    result = None
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=data, timeout=10) as resp:
            if resp.status != 200:
                raise Exception(f"Get OIDC token error: {resp.status}, full output is: {await resp.text()}")
            logger.info(f'full response is {await resp.text()}')
            result = await resp.json()
    return {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
    }


async def get_oidc_user(access_token: str, refresh_token: str) -> dict:
    if config["DEPLOY_MODE"] == 'local':
        ret = await get_local_oidc_user(access_token, refresh_token)
        return ret
    elif config["DEPLOY_MODE"] == 'gitee':
        ret = await get_gitee_oidc_user(access_token, refresh_token)
        return ret

    if not access_token:
        raise Exception("Access token is empty.")
    url = config['OIDC_USER_URL']
    headers = {
        "Authorization": access_token
    }

    result = None
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=10) as resp:
            if resp.status != 200:
                raise Exception(f"Get OIDC user error: {resp.status}, full response is: {resp.text()}")
            logger.info(f'full response is {await resp.text()}')
            result = await resp.json()

    if not result["phone_number_verified"]:
        raise Exception("Could not validate credentials.")
    
    user_sub = result['sub']
    with RedisConnectionPool.get_redis_connection() as r:
        r.set(f'{user_sub}_oidc_access_token', access_token, int(config['OIDC_ACCESS_TOKEN_EXPIRE_TIME'])*60)
        r.set(f'{user_sub}_oidc_refresh_token', refresh_token, int(config['OIDC_REFRESH_TOKEN_EXPIRE_TIME'])*60)

    return {
        "user_sub": user_sub
    }


async def get_local_oidc_token(code: str):
    data = {
        "client_id": config["OIDC_APP_ID"],
        "redirect_uri": config["EULER_LOGIN_API"],
        "grant_type": "authorization_code",
        "code": code
    }
    headers = {
        "Content-Type": "application/json"
    }
    url = config['OIDC_TOKEN_URL']
    result = None
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data, timeout=10) as resp:
            if resp.status != 200:
                raise Exception(f"Get OIDC token error: {resp.status}, full response is: {resp.text()}")
            logger.info(f'full response is {await resp.text()}')
            result = await resp.json()
    return {
        "access_token": result["data"]["access_token"],
        "refresh_token": result["data"]["refresh_token"],
    }


async def get_local_oidc_user(access_token: str, refresh_token: str) -> dict:
    if not access_token:
        raise Exception("Access token is empty.")
    headers = {
        "Content-Type": "application/json"
    }
    url = config['OIDC_USER_URL']
    data = {
        "token": access_token,
        "client_id": config["OIDC_APP_ID"],
    }
    result = None
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data, timeout=10) as resp:
            if resp.status != 200:
                raise Exception(f"Get OIDC user error: {resp.status}, full response is: {resp.text()}")
            logger.info(f'full response is {await resp.text()}')
            result = await resp.json()
    user_sub = result['data']
    with RedisConnectionPool.get_redis_connection() as r:
        r.set(
            f'{user_sub}_oidc_access_token', 
            access_token, 
            int(config['OIDC_ACCESS_TOKEN_EXPIRE_TIME'])*60
        )
        r.set(
            f'{user_sub}_oidc_refresh_token', 
            refresh_token, 
            int(config['OIDC_REFRESH_TOKEN_EXPIRE_TIME'])*60
        )

    return {
        "user_sub": user_sub
    }


async def get_gitee_oidc_user(access_token: str, refresh_token: str) -> dict:
    if not access_token:
        raise Exception("Access token is empty.")

    url = f'''{config['OIDC_USER_URL']}?access_token={access_token}'''
    result = None
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                raise Exception(f"Get OIDC user error: {resp.status}, full response is: {resp.text()}")
            logger.info(f'full response is {await resp.text()}')
            result = await resp.json()
    
    user_sub = result['login']
    if not GiteeIDManager.check_user_exist_or_not(user_sub):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="auth error"
        )
    with RedisConnectionPool.get_redis_connection() as r:
        r.set(f'{user_sub}_oidc_access_token', access_token, int(config['OIDC_ACCESS_TOKEN_EXPIRE_TIME'])*60)
        r.set(f'{user_sub}_oidc_refresh_token', refresh_token, int(config['OIDC_REFRESH_TOKEN_EXPIRE_TIME'])*60)

    return {
        "user_sub": user_sub
    }

