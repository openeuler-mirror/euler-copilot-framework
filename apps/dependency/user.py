# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户鉴权"""

import logging

from starlette import status
from starlette.exceptions import HTTPException
from starlette.requests import HTTPConnection

from apps.common.config import config
from apps.services.personal_token import PersonalTokenManager
from apps.services.session import SessionManager
from apps.services.user import UserManager

logger = logging.getLogger(__name__)


async def verify_session(request: HTTPConnection) -> None:
    """
    验证Session是否已鉴权；作为第一层鉴权检查

    - 如果Authorization头不存在或不以Bearer开头，抛出401
    - 如果Bearer token以sk-开头，跳过（由verify_personal_token处理）
    - 如果Bearer token不以sk-开头，则作为Session ID校验
    - 如果是合法session则设置user_id

    :param request: HTTP请求
    :return:
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        logger.warning("鉴权失败：缺少Authorization头")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="鉴权失败")

    if not auth_header.startswith("Bearer "):
        logger.warning("鉴权失败：Authorization格式错误，需要Bearer token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="鉴权失败：需要Bearer token",
        )

    token = auth_header.split(" ", 1)[1]

    # 如果以sk-开头，说明是Personal Token，跳过由verify_personal_token处理
    if token.startswith("sk-"):
        return

    # 作为Session ID校验
    request.state.session_id = token
    user_id = await SessionManager.get_user(token)
    if not user_id:
        logger.warning("Session ID鉴权失败：无效的session_id=%s", token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID 鉴权失败",
        )
    request.state.user_id = user_id


async def verify_personal_token(request: HTTPConnection) -> None:
    """
    验证Personal Token是否有效；作为第二层鉴权检查

    - 如果已经通过verify_session设置了user_id，则跳过
    - 如果Bearer token以sk-开头，则作为Personal Token校验
    - 合法则设置user_id，不合法则抛出401

    :param request: HTTP请求
    :return:
    """
    # 如果已经通过Session验证，则跳过
    if hasattr(request.state, "user_id"):
        return

    auth_header = request.headers.get("Authorization")
    # Authorization头格式已在verify_session中检查过
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("Personal Token鉴权失败：缺少或格式错误的Bearer token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Personal Token 鉴权失败：需要Bearer token",
        )

    token = auth_header.split(" ", 1)[1]

    # 检查是否为Personal Token（以sk-开头）
    if token.startswith("sk-"):
        # 验证是否为合法的Personal Token
        user_id = await PersonalTokenManager.get_user_by_personal_token(token)
        if user_id is not None:
            request.state.personal_token = token
            request.state.user_id = user_id
        else:
            # Personal Token无效，抛出401
            logger.warning("Personal Token鉴权失败：无效的token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Personal Token 鉴权失败",
            )

async def verify_admin(request: HTTPConnection) -> None:
    """验证用户是否为管理员"""
    if not hasattr(request.state, "user_id"):
        logger.warning("管理员鉴权失败：用户未登录")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户未登录")
    user_id = request.state.user_id
    user = await UserManager.get_user(user_id)
    request.state.user = user
    if not user:
        logger.warning("管理员鉴权失败：用户不存在，user_id=%s", user_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    if user.userName not in config.login.admin_user:
        logger.warning("管理员鉴权失败：用户无管理员权限，user_id=%s", user_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户无权限")
