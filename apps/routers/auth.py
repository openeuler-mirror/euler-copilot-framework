# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 用户认证相关路由"""

import grp
import logging

from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from apps.dependency import is_admin, verify_personal_token
from apps.schemas.personal_token import PostPersonalTokenMsg, PostPersonalTokenRsp
from apps.schemas.response_data import ResponseData
from apps.services.personal_token import PersonalTokenManager
from apps.services.user import UserManager

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)
_logger = logging.getLogger(__name__)


def _check_user_group(username: str) -> bool:
    """
    检查用户是否允许登录

    允许登录的条件:
    1. 用户id为0 (root用户)
    2. 用户在"wheel"组中
    3. 用户在"oi"组中

    :param username: Linux用户名
    :return: 如果用户允许登录返回True，否则返回False
    """
    # 先检查是否是管理员（root用户或wheel组）
    if is_admin(username):
        return True

    # 检查是否在oi组中
    try:
        oi_group = grp.getgrnam("oi")
        if username in oi_group.gr_mem:
            return True
    except KeyError:
        _logger.warning("[auth] 系统中未找到用户组 'oi'")
    except OSError:
        _logger.exception("[auth] 访问用户组 'oi' 信息时出错")

    return False


@router.get("/login")
async def linux_login(request: Request) -> JSONResponse:
    """
    GET /auth/login: Linux用户登录EulerCopilot

    通过检查X-Remote-User header和用户组验证用户身份

    :param request: Request object
    :return: JSONResponse
    """
    # 检查X-Remote-User header是否存在
    username = request.headers.get("X-Remote-User")
    if not username:
        _logger.warning("[auth] 未找到 X-Remote-User header")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_401_UNAUTHORIZED,
                    message="无法获取用户信息",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )

    # 检查用户是否在oi组中
    if not _check_user_group(username):
        _logger.warning("[auth] 用户 %s 不在 'oi' 组中，登录失败", username)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_403_FORBIDDEN,
                    message="您没有权限访问此系统",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )

    # 使用username作为user_id
    user_id = username

    # 创建或更新用户登录信息
    await UserManager.create_or_update_on_login(user_id, username)

    # 创建PersonalToken
    personal_token = await PersonalTokenManager.update_personal_token(user_id)
    if not personal_token:
        _logger.error("[auth] 用户 %s 创建PersonalToken失败", username)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="创建Token失败",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )

    _logger.info("[auth] 用户 %s 登录成功", username)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ResponseData(
                code=status.HTTP_200_OK,
                message="登录成功",
                result={"token": personal_token},
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@router.post("/key",
    dependencies=[Depends(verify_personal_token)],
    responses={
    400: {"model": ResponseData},
}, response_model=PostPersonalTokenRsp)
async def change_personal_token(request: Request) -> JSONResponse:
    """POST /auth/key: 重置用户的API密钥"""
    new_api_key: str | None = await PersonalTokenManager.update_personal_token(request.state.user_id)
    if not new_api_key:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=jsonable_encoder(
            ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="failed to update personal token",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        ))

    return JSONResponse(status_code=status.HTTP_200_OK, content=jsonable_encoder(
        PostPersonalTokenRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=PostPersonalTokenMsg(
                api_key=new_api_key,
            ),
        ).model_dump(exclude_none=True, by_alias=True),
    ))
