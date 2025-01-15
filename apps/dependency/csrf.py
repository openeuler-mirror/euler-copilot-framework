"""CSRF Token校验

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Optional

from fastapi import HTTPException, Request, Response, status

from apps.common.config import config
from apps.manager.session import SessionManager


async def verify_csrf_token(request: Request, response: Response) -> Optional[Response]:
    """验证CSRF Token"""
    if not config["ENABLE_CSRF"]:
        return None

    csrf_token = request.headers["x-csrf-token"].strip('"')
    session = request.cookies["ECSESSION"]

    if not await SessionManager.verify_csrf_token(session, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token is invalid.")

    new_csrf_token = await SessionManager.create_csrf_token(session)
    if not new_csrf_token:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Renew CSRF token failed.")

    if config["COOKIE_MODE"] == "DEBUG":
        response.set_cookie("_csrf_tk", new_csrf_token, max_age=config["SESSION_TTL"] * 60,
                            domain=config["DOMAIN"])
    else:
        response.set_cookie("_csrf_tk", new_csrf_token, max_age=config["SESSION_TTL"] * 60,
                            secure=True, domain=config["DOMAIN"], samesite="strict")
    return response

