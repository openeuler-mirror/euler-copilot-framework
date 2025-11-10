# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 用户认证相关路由"""

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from apps.common.oidc import oidc_provider
from apps.dependency import verify_personal_token, verify_session
from apps.schemas.personal_token import PostPersonalTokenMsg, PostPersonalTokenRsp
from apps.schemas.response_data import (
    OidcRedirectMsg,
    OidcRedirectRsp,
    ResponseData,
)
from apps.services.personal_token import PersonalTokenManager
from apps.services.session import SessionManager
from apps.services.token import TokenManager
from apps.services.user import UserManager

admin_router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)
router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
    dependencies=[Depends(verify_session), Depends(verify_personal_token)],
)
_logger = logging.getLogger(__name__)
_templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@admin_router.get("/login")
async def oidc_login(request: Request, code: str) -> HTMLResponse:
    """
    GET /auth/login?code=xxx: 用户登录EulerCopilot

    :param request: Request object
    :param code: OIDC code
    :return: HTMLResponse
    """
    try:
        token = await oidc_provider.get_oidc_token(code)
        user_info = await oidc_provider.get_oidc_user(token["access_token"])

        user_id: str | None = user_info.get("user_sub", None)
        if user_id:
            await oidc_provider.set_token(user_id, token["access_token"], token["refresh_token"])
    except Exception as e:
        _logger.exception("User login failed")
        status_code = status.HTTP_400_BAD_REQUEST if "auth error" in str(e) else status.HTTP_403_FORBIDDEN
        return _templates.TemplateResponse(
            "login_failed.html.j2",
            {"request": request, "reason": "无法验证登录信息，请关闭本窗口并重试。"},
            status_code=status_code,
        )
    # 获取用户信息
    if not request.client:
        return _templates.TemplateResponse(
            "login_failed.html.j2",
            {"request": request, "reason": "无法获取用户信息，请关闭本窗口并重试。"},
            status_code=status.HTTP_403_FORBIDDEN,
        )
    user_host = request.client.host
    # 获取用户sub
    if not user_id:
        _logger.error("OIDC no user_sub associated.")
        return _templates.TemplateResponse(
            "login_failed.html.j2",
            {"request": request, "reason": "未能获取用户信息，请关闭本窗口并重试。"},
            status_code=status.HTTP_403_FORBIDDEN,
        )
    # 创建或更新用户登录信息
    user_name: str | None = user_info.get("user_name", None)
    await UserManager.create_or_update_on_login(user_id, user_name)
    # 创建会话
    current_session = await SessionManager.create_session(user_id, user_host)
    return _templates.TemplateResponse(
        "login_success.html.j2",
        {"request": request, "current_session": current_session},
    )

# 用户主动logout
@router.get("/logout", response_model=ResponseData)
async def logout(request: Request) -> JSONResponse:
    """GET /auth/logout: 用户登出EulerCopilot"""
    if not request.client:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="IP error",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    await TokenManager.delete_plugin_token(request.state.user_id)

    if hasattr(request.state, "session_id"):
        await SessionManager.delete_session(request.state.session_id)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ResponseData(
                code=status.HTTP_200_OK,
                message="success",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@admin_router.get("/redirect", response_model=OidcRedirectRsp)
async def oidc_redirect() -> JSONResponse:
    """GET /auth/redirect: 前端获取OIDC重定向URL"""
    redirect_url = await oidc_provider.get_redirect_url()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            OidcRedirectRsp(
                code=status.HTTP_200_OK,
                message="success",
                result=OidcRedirectMsg(url=redirect_url),
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


# TODO(zwt): OIDC主动触发logout
@admin_router.post("/logout", response_model=ResponseData)
async def oidc_logout(token: Annotated[str, Body()]) -> JSONResponse:
    """POST /auth/logout: OIDC主动告知后端用户已在其他SSO站点登出"""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ResponseData(
                code=status.HTTP_200_OK,
                message="success",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@router.post("/key", responses={
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
