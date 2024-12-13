# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from apps.common.config import config
from apps.common.oidc import get_oidc_token, get_oidc_user
from apps.dependency.csrf import verify_csrf_token
from apps.dependency.user import get_user, verify_user
from apps.entities.request_data import ModifyRevisionData
from apps.entities.response_data import ResponseData
from apps.entities.user import User
from apps.manager.audit_log import AuditLogData, AuditLogManager
from apps.manager.session import SessionManager
from apps.manager.user import UserManager
from apps.models.redis import RedisConnectionPool

logger = logging.getLogger('gunicorn.error')

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"]
)


@router.get("/login", response_class=RedirectResponse)
async def oidc_login(request: Request, code: str, redirect_index: str = None):
    if redirect_index:
        response = RedirectResponse(redirect_index, status_code=301)
    else:
        response = RedirectResponse(config["WEB_FRONT_URL"], status_code=301)
    try:
        token = await get_oidc_token(code)
        user_info = await get_oidc_user(token["access_token"], token["refresh_token"])
        user_sub: str | None = user_info.get('user_sub', None)
    except Exception as e:
        logger.error(f"User login failed: {e}")
        if 'auth error' in str(e):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="auth error")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User login failed.")

    user_host = request.client.host
    if not user_sub:
        logger.error("OIDC no user_sub associated.")
        data = AuditLogData(method_type='get', source_name='/authorize/login',
                            ip=user_host, result='fail', reason="OIDC no user_sub associated.")
        AuditLogManager.add_audit_log('None', data)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User login failed.")

    UserManager.update_userinfo_by_user_sub(User(**user_info))

    current_session = request.cookies.get("ECSESSION")
    try:
        SessionManager.delete_session(current_session)
        current_session = SessionManager.create_session(user_host, extra_keys={
            "user_sub": user_sub
        })
    except Exception as e:
        logger.error(f"Change session failed: {e}")
        data = AuditLogData(method_type='get', source_name='/authorize/login',
                            ip=user_host, result='fail', reason="Change session failed.")
        AuditLogManager.add_audit_log(user_sub, data)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User login failed.")

    new_csrf_token = SessionManager.create_csrf_token(current_session)
    if config['COOKIE_MODE'] == 'DEBUG':
        response.set_cookie(
            "_csrf_tk", 
            new_csrf_token
        )
        response.set_cookie(
            "ECSESSION", 
            current_session
        )
    else:
        response.set_cookie(
            "_csrf_tk", 
            new_csrf_token, 
            max_age=config["SESSION_TTL"] * 60,
            secure=True, 
            domain=config["DOMAIN"], 
            samesite="strict"
        )
        response.set_cookie(
            "ECSESSION", 
            current_session, 
            max_age=config["SESSION_TTL"] * 60,
            secure=True, 
            domain=config["DOMAIN"], 
            httponly=True, 
            samesite="strict"
        )
    data = AuditLogData(
        method_type='get', 
        source_name='/authorize/login',
        ip=user_host, 
        result='success', 
        reason="User login."
    )
    AuditLogManager.add_audit_log(user_sub, data)

    return response


# 用户主动logout
@router.get("/logout", response_model=ResponseData, dependencies=[Depends(verify_user), Depends(verify_csrf_token)])
async def logout(request: Request, response: Response, user: User = Depends(get_user)):
    session_id = request.cookies['ECSESSION']
    if not SessionManager.verify_user(session_id):
        logger.info("User already logged out.")
        return ResponseData(code=200, message="ok", result={})

    # 删除 oidc related token
    user_sub = user.user_sub
    with RedisConnectionPool.get_redis_connection() as r:
        r.delete(f'{user_sub}_oidc_access_token')
        r.delete(f'{user_sub}_oidc_refresh_token')
        r.delete(f'aops_{user_sub}_token')

    SessionManager.delete_session(session_id)
    new_session = SessionManager.create_session(request.client.host)

    response.set_cookie("ECSESSION", new_session, max_age=config["SESSION_TTL"] * 60,
                        httponly=True, secure=True, samesite="strict", domain=config["DOMAIN"])
    response.delete_cookie("_csrf_tk")

    data = AuditLogData(method_type='get', source_name='/authorize/logout',
                        ip=request.client.host, result='User logout succeeded.', reason='')
    AuditLogManager.add_audit_log(user.user_sub, data)
    return {
        "code": 200,
        "message": "success",
        "result": dict()
    }


@router.get("/redirect")
async def oidc_redirect():
    return {
        "code": 200,
        "message": "success",
        "result": config["OIDC_REDIRECT_URL"]
    }


@router.get("/user", dependencies=[Depends(verify_user)], response_model=ResponseData)
async def userinfo(user: User = Depends(get_user)):
    revision_number = UserManager.get_revision_number_by_user_sub(user_sub=user.user_sub)
    user.revision_number = revision_number
    return {
        "code": 200,
        "message": "success",
        "result": user.__dict__
    }


@router.post("/update_revision_number", dependencies=[Depends(verify_user), Depends(verify_csrf_token)],
             response_model=ResponseData)
async def update_revision_number(post_body: ModifyRevisionData, user: User = Depends(get_user)):
    user.revision_number = post_body.revision_num
    ret = UserManager.update_userinfo_by_user_sub(user, refresh_revision=True)
    return {
        "code": 200,
        "message": "success",
        "result": ret.__dict__
    }
