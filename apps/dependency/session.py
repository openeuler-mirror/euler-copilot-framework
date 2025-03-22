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

    def _check_bypass_list(self, path: str) -> bool:
        """检查请求路径是否需要跳过验证"""
        return path in BYPASS_LIST

    def _validate_client(self, request: Request) -> str:
        """验证客户端信息并返回主机地址"""
        if request.client is None or request.client.host is None:
            err = "[VerifySessionMiddleware] 无法检测请求来源IP！"
            raise ValueError(err)
        return request.client.host

    def _update_cookie_header(self, request: Request, session_id: str) -> None:
        """更新请求头中的cookie信息"""
        cookie_str = ""
        for item in request.scope["headers"]:
            if item[0] == b"cookie":
                cookie_str = item[1].decode()
                request.scope["headers"].remove(item)
                break

        all_cookies = ""
        if cookie_str:
            other_headers = cookie_str.split(";")
            all_cookies = "; ".join(item for item in other_headers if "ECSESSION" not in item)

        all_cookies = f"{all_cookies}; ECSESSION={session_id}" if all_cookies else f"ECSESSION={session_id}"
        request.scope["headers"].append((b"cookie", all_cookies.encode()))

    def _set_response_cookie(self, response: Response, session_id: str) -> None:
        """设置响应cookie"""
        cookie_params = {
            "key": "ECSESSION",
            "value": session_id,
            "domain": config["DOMAIN"],
        }

        if config["COOKIE_MODE"] != "DEBUG":
            cookie_params.update({
                "httponly": True,
                "secure": True,
                "samesite": "strict",
                "max_age": config["SESSION_TTL"] * 60,
            })

        response.set_cookie(**cookie_params)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """浏览器Session校验中间件"""
        if self._check_bypass_list(request.url.path):
            return await call_next(request)

        host = self._validate_client(request)
        cookie = request.cookies.get("ECSESSION", "")
        session_id = await SessionManager.get_session(cookie, host)

        if session_id != cookie:
            self._update_cookie_header(request, session_id)

        response = await call_next(request)
        self._set_response_cookie(response, session_id)
        return response
