"""浏览器Session校验

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from fastapi import Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request

from apps.common.config import config
from apps.manager.session import SessionManager

BYPASS_LIST = [
    "/health_check",
    "/api/auth/login",
    "/api/auth/logout",
]


class VerifySessionMiddleware(BaseHTTPMiddleware):
    """浏览器Session校验中间件"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:  # noqa: C901, PLR0912
        """浏览器Session校验中间件"""
        if request.url.path in BYPASS_LIST:
            return await call_next(request)

        # TODO: 加入apikey校验
        cookie = request.cookies.get("ECSESSION", "")
        if request.client is None or request.client.host is None:
            err = "无法检测请求来源IP！"
            raise ValueError(err)
        host = request.client.host
        session_id = await SessionManager.get_session(cookie, host)

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
                        all_cookies += f"{item}; "

            all_cookies += f"ECSESSION={session_id}"
            request.scope["headers"].append((b"cookie", all_cookies.encode()))

            response = await call_next(request)
            if config["COOKIE_MODE"] == "DEBUG":
                response.set_cookie("ECSESSION", session_id, domain=config["DOMAIN"])
            else:
                response.set_cookie("ECSESSION", session_id, httponly=True, secure=True, samesite="strict",
                                    max_age=config["SESSION_TTL"] * 60, domain=config["DOMAIN"])
        else:
            response = await call_next(request)
            if config["COOKIE_MODE"] == "DEBUG":
                response.set_cookie("ECSESSION", session_id, domain=config["DOMAIN"])
            else:
                response.set_cookie("ECSESSION", session_id, httponly=True, secure=True, samesite="strict",
                                    max_age=config["SESSION_TTL"] * 60, domain=config["DOMAIN"])
        return response
