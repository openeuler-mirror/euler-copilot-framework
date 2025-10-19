# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""全局异常处理中间件"""

import logging
import traceback
from typing import Any, Dict

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException, RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """全局错误处理中间件"""
    
    async def dispatch(self, request: Request, call_next):
        """处理请求并捕获异常"""
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            return await self.handle_exception(request, exc)
    
    async def handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """处理异常并返回适当的响应"""
        
        # 获取请求信息用于日志
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        url = str(request.url)
        
        # 根据异常类型返回不同的响应
        if isinstance(exc, HTTPException):
            # FastAPI HTTPException
            logger.warning(
                f"HTTP异常 - {method} {url} - IP: {client_ip} - "
                f"状态码: {exc.status_code} - 详情: {exc.detail}"
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": {
                        "code": exc.status_code,
                        "message": exc.detail,
                        "type": "HTTPException"
                    }
                }
            )
        
        elif isinstance(exc, StarletteHTTPException):
            # Starlette HTTPException
            logger.warning(
                f"Starlette HTTP异常 - {method} {url} - IP: {client_ip} - "
                f"状态码: {exc.status_code} - 详情: {exc.detail}"
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": {
                        "code": exc.status_code,
                        "message": exc.detail,
                        "type": "HTTPException"
                    }
                }
            )
        
        elif isinstance(exc, RequestValidationError):
            # 请求验证错误
            logger.warning(
                f"请求验证错误 - {method} {url} - IP: {client_ip} - "
                f"错误: {exc.errors()}"
            )
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "error": {
                        "code": 422,
                        "message": "请求参数验证失败",
                        "details": exc.errors(),
                        "type": "ValidationError"
                    }
                }
            )
        
        elif isinstance(exc, ValueError):
            # 业务逻辑错误（通常来自我们的代码）
            error_msg = str(exc)
            logger.error(
                f"业务逻辑错误 - {method} {url} - IP: {client_ip} - "
                f"错误: {error_msg}"
            )
            
            # 根据错误消息判断具体的错误类型
            status_code = status.HTTP_400_BAD_REQUEST
            error_type = "ValueError"
            
            if "认证失败" in error_msg or "API密钥" in error_msg:
                status_code = status.HTTP_401_UNAUTHORIZED
                error_type = "AuthenticationError"
            elif "余额不足" in error_msg or "欠费" in error_msg:
                status_code = status.HTTP_402_PAYMENT_REQUIRED
                error_type = "PaymentRequired"
            elif "频率超限" in error_msg or "限制" in error_msg:
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
                error_type = "RateLimitError"
            elif "连接" in error_msg or "网络" in error_msg:
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
                error_type = "ConnectionError"
            elif "超时" in error_msg:
                status_code = status.HTTP_504_GATEWAY_TIMEOUT
                error_type = "TimeoutError"
            
            return JSONResponse(
                status_code=status_code,
                content={
                    "error": {
                        "code": status_code,
                        "message": error_msg,
                        "type": error_type
                    }
                }
            )
        
        elif isinstance(exc, PermissionError):
            # 权限错误
            logger.warning(
                f"权限错误 - {method} {url} - IP: {client_ip} - "
                f"错误: {str(exc)}"
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": {
                        "code": 403,
                        "message": str(exc) or "权限不足",
                        "type": "PermissionError"
                    }
                }
            )
        
        elif isinstance(exc, FileNotFoundError):
            # 文件未找到错误
            logger.warning(
                f"文件未找到 - {method} {url} - IP: {client_ip} - "
                f"错误: {str(exc)}"
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": {
                        "code": 404,
                        "message": "请求的资源不存在",
                        "type": "NotFoundError"
                    }
                }
            )
        
        else:
            # 未知异常
            error_id = id(exc)  # 生成唯一错误ID用于追踪
            logger.error(
                f"未知异常 [ID: {error_id}] - {method} {url} - IP: {client_ip} - "
                f"异常类型: {type(exc).__name__} - 错误: {str(exc)}\n"
                f"堆栈跟踪:\n{traceback.format_exc()}"
            )
            
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": {
                        "code": 500,
                        "message": "服务器内部错误，请稍后重试",
                        "error_id": error_id,
                        "type": "InternalServerError"
                    }
                }
            )


def create_error_handlers() -> Dict[Any, Any]:
    """创建错误处理器字典"""
    
    async def http_exception_handler(request: Request, exc: HTTPException):
        """HTTP异常处理器"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.status_code,
                    "message": exc.detail,
                    "type": "HTTPException"
                }
            }
        )
    
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """请求验证异常处理器"""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": 422,
                    "message": "请求参数验证失败",
                    "details": exc.errors(),
                    "type": "ValidationError"
                }
            }
        )
    
    async def general_exception_handler(request: Request, exc: Exception):
        """通用异常处理器"""
        error_id = id(exc)
        logger.error(
            f"未处理异常 [ID: {error_id}] - {request.method} {request.url} - "
            f"异常类型: {type(exc).__name__} - 错误: {str(exc)}\n"
            f"堆栈跟踪:\n{traceback.format_exc()}"
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": 500,
                    "message": "服务器内部错误，请稍后重试",
                    "error_id": error_id,
                    "type": "InternalServerError"
                }
            }
        )
    
    return {
        HTTPException: http_exception_handler,
        RequestValidationError: validation_exception_handler,
        Exception: general_exception_handler,
    }
