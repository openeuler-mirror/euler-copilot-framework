"""用户鉴权

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from starlette import status
from starlette.exceptions import HTTPException
from starlette.requests import HTTPConnection

from apps.common.oidc import oidc_provider
from apps.manager.api_key import ApiKeyManager
from apps.manager.session import SessionManager

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def verify_user(request: HTTPConnection) -> None:
    """验证Session是否已鉴权；未鉴权则抛出HTTP 401；接口级dependence

    :param request: HTTP请求
    :return:
    """
    session_id = request.cookies["ECSESSION"]
    if not await SessionManager.verify_user(session_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication Error.")

async def get_session(request: HTTPConnection) -> str:
    """验证Session是否已鉴权，并返回Session ID；未鉴权则抛出HTTP 401；参数级dependence

    :param request: HTTP请求
    :return: Session ID
    """
    session_id = request.cookies["ECSESSION"]
    if not await SessionManager.verify_user(session_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication Error.")
    return session_id

async def get_user(request: HTTPConnection) -> str:
    """验证Session是否已鉴权；若已鉴权，查询对应的user_sub；若未鉴权，抛出HTTP 401；参数级dependence

    :param request: HTTP请求体
    :return: 用户sub
    """
    session_id = request.cookies["ECSESSION"]
    user = await SessionManager.get_user(session_id)
    if user:
        return user

    # 没有用户，则尝试OIDC检查状态
    tokens = await oidc_provider.get_login_status(request.cookies)
    if not tokens:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="[OIDC] 检查OIDC登录状态失败")

    # 获取用户信息
    user_info = await oidc_provider.get_oidc_user(tokens["access_token"])
    if not user_info:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="[OIDC] 获取用户信息失败")

    return user_info["user_sub"]


async def verify_api_key(api_key: str = Depends(oauth2_scheme)) -> None:
    """验证API Key是否有效；无效则抛出HTTP 401；接口级dependence

    :param api_key: API Key
    :return:
    """
    if not await ApiKeyManager.verify_api_key(api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key!")


async def get_user_by_api_key(api_key: str = Depends(oauth2_scheme)) -> str:
    """验证API Key是否有效；若有效，返回对应的user_sub；若无效，抛出HTTP 401；参数级dependence

    :param api_key: API Key
    :return: 用户sub
    """
    user_sub = await ApiKeyManager.get_user_by_api_key(api_key)
    if user_sub is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key!")
    return user_sub
