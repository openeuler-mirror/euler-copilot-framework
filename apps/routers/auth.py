# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 用户认证相关路由"""

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from apps.common.config import Config
from apps.common.oidc import oidc_provider
from apps.dependency import get_session, get_user, verify_user
from apps.schemas.collection import Audit
from apps.schemas.response_data import (
    AuthUserMsg,
    AuthUserRsp,
    OidcRedirectMsg,
    OidcRedirectRsp,
    ResponseData,
)
from apps.services.audit_log import AuditLogManager
from apps.services.session import SessionManager
from apps.services.token import TokenManager
from apps.services.user import UserManager

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)
logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/login")
async def oidc_login(request: Request, code: str) -> HTMLResponse:
    """
    OIDC login

    :param request: Request object
    :param code: OIDC code
    :return: HTMLResponse
    """
    try:
        token = await oidc_provider.get_oidc_token(code)
        user_info = await oidc_provider.get_oidc_user(token["access_token"])

        user_sub: str | None = user_info.get("user_sub", None)
    except Exception as e:
        logger.exception("User login failed")
        status_code = status.HTTP_400_BAD_REQUEST if "auth error" in str(e) else status.HTTP_403_FORBIDDEN
        return templates.TemplateResponse(
            "login_failed.html.j2",
            {"request": request, "reason": "无法验证登录信息，请关闭本窗口并重试。"},
            status_code=status_code,
        )

    user_host = request.client.host if request.client else None

    if not user_sub:
        logger.error("OIDC no user_sub associated.")
        data = Audit(
            http_method="get",
            module="auth",
            client_ip=user_host,
            message="/api/auth/login: OIDC no user_sub associated.",
        )
        await AuditLogManager.add_audit_log(data)
        return templates.TemplateResponse(
            "login_failed.html.j2",
            {"request": request, "reason": "未能获取用户信息，请关闭本窗口并重试。"},
            status_code=status.HTTP_403_FORBIDDEN,
        )

    await UserManager.update_userinfo_by_user_sub(user_sub)

    current_session = await SessionManager.create_session(user_host, user_sub)

    data = Audit(
        user_sub=user_sub,
        http_method="get",
        module="auth",
        client_ip=user_host,
        message="/api/auth/login: User login.",
    )
    await AuditLogManager.add_audit_log(data)

    return templates.TemplateResponse(
        "login_success.html.j2",
        {"request": request, "current_session": current_session},
    )


# 用户主动logout
@router.get("/logout", response_model=ResponseData)
async def logout(
    request: Request,
    user_sub: Annotated[str, Depends(get_user)],
    session_id: Annotated[str, Depends(get_session)],
) -> JSONResponse:
    """用户登出EulerCopilot"""
    if not request.client:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="IP error",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    await TokenManager.delete_plugin_token(user_sub)
    await SessionManager.delete_session(session_id)

    data = Audit(
        http_method="get",
        module="auth",
        client_ip=request.client.host,
        user_sub=user_sub,
        message="/api/auth/logout: User logout succeeded.",
    )
    await AuditLogManager.add_audit_log(data)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result={},
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.get("/redirect", response_model=OidcRedirectRsp)
async def oidc_redirect() -> JSONResponse:
    """OIDC重定向URL"""
    redirect_url = await oidc_provider.get_redirect_url()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=OidcRedirectRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=OidcRedirectMsg(url=redirect_url),
        ).model_dump(exclude_none=True, by_alias=True),
    )


# TODO(zwt): OIDC主动触发logout
@router.post("/logout", dependencies=[Depends(verify_user)], response_model=ResponseData)
async def oidc_logout(token: str) -> JSONResponse:
    """OIDC主动触发登出"""


@router.get("/user", response_model=AuthUserRsp)
async def userinfo(
    user_sub: Annotated[str, Depends(get_user)],
    _: Annotated[None, Depends(verify_user)],
) -> JSONResponse:
    """获取用户信息"""
    user = await UserManager.get_userinfo_by_user_sub(user_sub=user_sub)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Get UserInfo failed.",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=AuthUserRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=AuthUserMsg(
                user_sub=user_sub,
                revision=user.is_active,
                is_admin=user.is_admin,
            ),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.post(
    "/update_revision_number",
    dependencies=[Depends(verify_user)],
    response_model=AuthUserRsp,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ResponseData},
    },
)
async def update_revision_number(request: Request, user_sub: Annotated[str, Depends(get_user)]) -> JSONResponse:  # noqa: ARG001
    """更新用户协议信息"""
    ret: bool = await UserManager.update_userinfo_by_user_sub(user_sub, refresh_revision=True)
    if not ret:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="update revision failed",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )

    user = await UserManager.get_userinfo_by_user_sub(user_sub)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Get UserInfo failed.",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=AuthUserRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=AuthUserMsg(
                user_sub=user_sub,
                revision=user.is_active,
                is_admin=user.is_admin,
            ),
        ).model_dump(exclude_none=True, by_alias=True),
    )
