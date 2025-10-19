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
async def oidc_login(request: Request, code: str = None, error: str = None, error_description: str = None) -> HTMLResponse:
    """
    OIDC login callback

    :param request: Request object
    :param code: OIDC authorization code (success case)
    :param error: OAuth2 error code (failure case)
    :param error_description: OAuth2 error description (failure case)
    :return: HTMLResponse
    """
    # Handle OAuth2 error response
    if error:
        logger.warning(f"OAuth2 authorization failed: {error} - {error_description}")
        
        # Handle different error types
        if error == "access_denied":
            reason = "授权被拒绝，请重新登录。"
        elif error == "invalid_request":
            reason = "请求参数错误，请重试。"
        elif error == "unauthorized_client":
            reason = "客户端未授权，请联系管理员。"
        elif error == "unsupported_response_type":
            reason = "不支持的响应类型，请联系管理员。"
        elif error == "invalid_scope":
            reason = "权限范围无效，请联系管理员。"
        elif error == "server_error":
            reason = "服务器错误，请稍后重试。"
        elif error == "temporarily_unavailable":
            reason = "服务暂时不可用，请稍后重试。"
        else:
            reason = f"登录失败：{error_description or error}"
        
        return templates.TemplateResponse(
            "login_failed.html.j2",
            {"request": request, "reason": reason},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    
    # Handle missing code parameter
    if not code:
        logger.error("Neither code nor error parameter provided in OAuth2 callback")
        return templates.TemplateResponse(
            "login_failed.html.j2",
            {"request": request, "reason": "缺少必要的授权参数，请重新登录。"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    
    # Handle successful authorization (existing logic)
    try:
        token = await oidc_provider.get_oidc_token(code)
        user_info = await oidc_provider.get_oidc_user(token["access_token"])

        user_sub: str | None = user_info.get("user_sub", None)
        user_name: str = user_info.get("user_name", "")
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

    await UserManager.update_refresh_revision_by_user_sub(user_sub, user_name=user_name)

    current_session = await SessionManager.create_session(user_host, user_sub, user_name)

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
    
    # 先触发authHub的登出，清理authHub侧的cookie
    try:
        await oidc_provider.oidc_logout(dict(request.cookies))
        logger.info(f"AuthHub logout succeeded for user: {user_sub}")
    except Exception as e:
        logger.warning(f"AuthHub logout failed for user {user_sub}: {e}")
        # 即使authHub登出失败，也继续清理本地session，避免用户无法登出
    
    # 清理本地token和session
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
async def oidc_logout(token: str) -> JSONResponse | None:
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
                user_name=user.user_name,
                revision=user.is_active,
                is_admin=user.is_admin,
                auto_execute=user.auto_execute,
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
    ret: bool = await UserManager.update_refresh_revision_by_user_sub(user_sub, refresh_revision=True)
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
                user_name=user.user_name,
                revision=user.is_active,
                is_admin=user.is_admin,
                auto_execute=user.auto_execute,
            ),
        ).model_dump(exclude_none=True, by_alias=True),
    )
