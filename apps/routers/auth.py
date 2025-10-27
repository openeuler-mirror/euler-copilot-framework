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
async def oidc_login(request: Request, code: str = None, error: str = None, error_description: str = None):
    """
    统一的OIDC登录处理端点
    
    :param request: Request object
    :param code: OIDC authorization code (success case)
    :param error: OAuth2 error code (failure case)  
    :param error_description: OAuth2 error description (failure case)
    :return: JSONResponse for API calls, HTMLResponse for browser redirects
    """
    # 检查请求是否来自前端API调用（通过Accept头和User-Agent判断）
    accept_header = request.headers.get("accept", "")
    user_agent = request.headers.get("user-agent", "")
    
    # 如果明确请求JSON或者是axios等API客户端，则视为API请求
    is_api_request = (
        "application/json" in accept_header or
        "axios" in user_agent.lower() or
        "fetch" in user_agent.lower() or
        request.query_params.get("format") == "json"
    )
    
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
        
        if is_api_request:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message=reason,
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        else:
            return templates.TemplateResponse(
                "login_failed.html.j2",
                {"request": request, "reason": reason},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    
    # Handle missing code parameter
    if not code:
        logger.error("Neither code nor error parameter provided in OAuth2 callback")
        reason = "缺少必要的授权参数，请重新登录。"
        
        if is_api_request:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message=reason,
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        else:
            return templates.TemplateResponse(
                "login_failed.html.j2",
                {"request": request, "reason": reason},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    
    # Handle successful authorization
    try:
        token = await oidc_provider.get_oidc_token(code)
        user_info = await oidc_provider.get_oidc_user(token["access_token"])

        user_sub: str | None = user_info.get("user_sub", None)
        if Config().get_config().login.provider == "authelia":
            user_name: str = user_info.get("user_name", "")
        elif Config().get_config().login.provider == "authhub":
            user_name: str = user_sub
        else:
            user_name: str = user_info.get("username", "")
        if not user_name:
            user_name = user_sub
    except Exception as e:
        logger.exception("User login failed")
        reason = "无法验证登录信息，请重试。"
        error_status = status.HTTP_400_BAD_REQUEST if "auth error" in str(e) else status.HTTP_403_FORBIDDEN
        
        if is_api_request:
            return JSONResponse(
                status_code=error_status,
                content=ResponseData(
                    code=error_status,
                    message=reason,
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        else:
            return templates.TemplateResponse(
                "login_failed.html.j2",
                {"request": request, "reason": reason},
                status_code=error_status,
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
        reason = "未能获取用户信息，请重试。"
        
        if is_api_request:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content=ResponseData(
                    code=status.HTTP_403_FORBIDDEN,
                    message=reason,
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        else:
            return templates.TemplateResponse(
                "login_failed.html.j2",
                {"request": request, "reason": reason},
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

    # 统一返回session ID作为认证凭据
    if is_api_request:
        # API请求返回JSON，session ID作为token
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=ResponseData(
                code=status.HTTP_200_OK,
                message="success",
                result={"session_id": current_session},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    else:
        # 浏览器重定向返回HTML页面，用于弹窗场景
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
async def oidc_redirect(action: str = "login") -> JSONResponse:
    """OIDC重定向URL"""
    if action == "settings":
        # 直接读取配置中的redirect_settings_url
        from apps.common.config import Config
        config = Config().get_config()
        
        if hasattr(config.login.settings, 'redirect_settings_url') and config.login.settings.redirect_settings_url:
            # 直接使用配置文件中的redirect_settings_url
            redirect_url = config.login.settings.redirect_settings_url
        else:
            # 如果无法获取配置，返回特定响应提示
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="当前鉴权服务暂无用户主页",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
    else:
        # 默认返回登录URL
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
    
    # 当使用AuthHub且user_name为空时，使用user_sub作为显示名称
    display_name = user.user_name
    if (not display_name or display_name.strip() == "") and Config().get_config().login.provider == "authhub":
        display_name = user_sub
        logger.info(f"AuthHub用户 {user_sub} 的user_name为空，使用user_sub '{user_sub}' 作为显示名称")
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=AuthUserRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=AuthUserMsg(
                user_sub=user_sub,
                user_name=display_name,
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
