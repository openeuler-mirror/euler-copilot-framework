# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户鉴权"""

import grp
import logging
import pwd

from starlette import status
from starlette.exceptions import HTTPException
from starlette.requests import HTTPConnection

from apps.services.personal_token import PersonalTokenManager
from apps.services.user import UserManager

logger = logging.getLogger(__name__)


def is_admin(username: str) -> bool:
    """
    判断用户是否为管理员

    管理员条件:
    1. 用户id为0 (root用户)
    2. 用户在"wheel"组中

    :param username: Linux用户名
    :return: 如果用户是管理员返回True，否则返回False
    """
    try:
        user_info = pwd.getpwnam(username)
        if user_info.pw_uid == 0:
            return True
    except KeyError:
        logger.warning("系统中未找到用户 '%s'", username)
        return False
    except OSError:
        logger.exception("访问用户 %s 的信息时出错", username)
        return False

    # 检查是否在wheel组中
    try:
        wheel_group = grp.getgrnam("wheel")
        if username in wheel_group.gr_mem:
            return True
    except KeyError:
        logger.warning("系统中未找到用户组 'wheel'")
    except OSError:
        logger.exception("访问用户组 'wheel' 信息时出错")

    return False


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
    if not is_admin(user.userName):
        logger.warning("管理员鉴权失败：用户无管理员权限，user_id=%s", user_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户无权限")
