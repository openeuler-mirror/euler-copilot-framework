# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from fastapi import Request, HTTPException, status, Response

from apps.manager.session import SessionManager
from apps.common.config import config


def verify_csrf_token(request: Request, response: Response):
    if not config["ENABLE_CSRF"]:
        return

    csrf_token = request.headers.get('x-csrf-token').strip("\"")
    session = request.cookies.get('ECSESSION')

    if not SessionManager.verify_csrf_token(session, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='CSRF token is invalid.')

    new_csrf_token = SessionManager.create_csrf_token(session)
    if not new_csrf_token:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Renew CSRF token failed.")

    response.set_cookie("_csrf_tk", new_csrf_token, max_age=config["SESSION_TTL"] * 60,
                        secure=True, domain=config["DOMAIN"], samesite="strict")
    return response
