"""
身份传递模块

处理 UDS IPC 请求中的用户身份信息传递。

设计说明：
- 仅支持本机 UDS 连接，无需复杂的 token 验证
- 通过 X-Witty-User header 传递用户 ID
- 通过 X-Witty-Session header 传递会话 ID（可选）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Header, HTTPException, Request

logger = logging.getLogger(__name__)

# HTTP Headers
HEADER_USER_ID = "X-Witty-User"
HEADER_SESSION_ID = "X-Witty-Session"
HEADER_REQUEST_ID = "X-Request-ID"

# 默认用户（仅用于系统级操作）
SYSTEM_USER_ID = "__system__"

# 用户 ID 最大长度
MAX_USER_ID_LENGTH = 128


@dataclass
class UserContext:
    """
    用户上下文

    封装请求中的用户身份信息
    """

    user_id: str
    session_id: str | None = None
    request_id: str | None = None
    authenticated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_system(self) -> bool:
        """是否为系统用户"""
        return self.user_id == SYSTEM_USER_ID

    def __str__(self) -> str:
        """字符串表示"""
        if self.session_id:
            return f"UserContext(user={self.user_id}, session={self.session_id})"
        return f"UserContext(user={self.user_id})"


async def get_user_context(
    request: Request,
    x_witty_user: Annotated[str | None, Header(alias=HEADER_USER_ID)] = None,
    x_witty_session: Annotated[str | None, Header(alias=HEADER_SESSION_ID)] = None,
    x_request_id: Annotated[str | None, Header(alias=HEADER_REQUEST_ID)] = None,
) -> UserContext:
    """
    从请求中提取用户上下文

    Args:
        request: FastAPI 请求对象
        x_witty_user: 用户 ID header
        x_witty_session: 会话 ID header
        x_request_id: 请求 ID header

    Returns:
        用户上下文

    Raises:
        HTTPException: 缺少必要的身份信息

    """
    # 检查 UDS 连接（生产环境应验证）
    # 在开发环境允许 TCP 连接
    client_host = request.client.host if request.client else "unknown"

    # 获取用户 ID
    user_id = x_witty_user
    if not user_id:
        logger.warning(
            "Missing %s header from %s, path=%s",
            HEADER_USER_ID,
            client_host,
            request.url.path,
        )
        raise HTTPException(
            status_code=401,
            detail={
                "code": "MISSING_USER_IDENTITY",
                "message": f"Missing required header: {HEADER_USER_ID}",
            },
        )

    # 验证用户 ID 格式（简单验证）
    if not _is_valid_user_id(user_id):
        logger.warning(
            "Invalid user ID format: %s from %s",
            user_id,
            client_host,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_USER_ID",
                "message": "User ID contains invalid characters",
            },
        )

    context = UserContext(
        user_id=user_id,
        session_id=x_witty_session,
        request_id=x_request_id,
    )

    logger.debug("Authenticated user: %s", context)
    return context


def _is_valid_user_id(user_id: str) -> bool:
    """
    验证用户 ID 格式

    允许：字母、数字、下划线、连字符、点号
    长度：1-MAX_USER_ID_LENGTH 字符
    """
    if not user_id or len(user_id) > MAX_USER_ID_LENGTH:
        return False

    # 允许的字符
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")
    return all(c in allowed_chars for c in user_id)


def create_system_context(request_id: str | None = None) -> UserContext:
    """
    创建系统用户上下文

    用于内部操作，不需要用户身份

    Args:
        request_id: 请求 ID

    Returns:
        系统用户上下文

    """
    return UserContext(
        user_id=SYSTEM_USER_ID,
        request_id=request_id,
    )
