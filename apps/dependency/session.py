# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from apps.manager.session import SessionManager
from apps.common.config import config


BYPASS_LIST = [
    "/health_check",
    "/api/auth/login",
    "/api/auth/logout",
]


class VerifySessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in BYPASS_LIST:
            return await call_next(request)

        cookie = request.cookies.get("ECSESSION", "")
        host = request.client.host
        session_id = SessionManager.get_session(cookie, host)

        if session_id != request.cookies.get("ECSESSION", ""):
            cookie_str = ""

            for item in request.scope["headers"]:
                if item[0] == b"cookie":
                    cookie_str = item[1].decode()
                    request.scope["headers"].remove(item)
                    break

            all_cookies = ""
            if cookie_str != "":
                other_headers = cookie_str.split(";")
                for item in other_headers:
                    if "ECSESSION" not in item:
                        all_cookies += "{}; ".format(item)

            all_cookies += "ECSESSION={}".format(session_id)
            request.scope["headers"].append((b"cookie", all_cookies.encode()))

            response = await call_next(request)
            response.set_cookie("ECSESSION", session_id, httponly=True, secure=True, samesite="strict",
                                max_age=config["SESSION_TTL"] * 60, domain=config["DOMAIN"])
        else:
            response = await call_next(request)
            response.set_cookie("ECSESSION", session_id, httponly=True, secure=True, samesite="strict",
                                max_age=config["SESSION_TTL"] * 60, domain=config["DOMAIN"])
        return response
