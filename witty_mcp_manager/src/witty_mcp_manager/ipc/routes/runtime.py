"""
Runtime 路由

提供运行时会话状态查询 API。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam

from witty_mcp_manager.ipc.auth import UserContext, get_user_context
from witty_mcp_manager.ipc.schemas import (
    RuntimeListResponse,
    RuntimeStatus,
    RuntimeStatusResponse,
)

if TYPE_CHECKING:
    from witty_mcp_manager.ipc.server import IPCServer

router = APIRouter(prefix="/v1/runtime", tags=["Runtime"])

# 服务器实例引用
_server: IPCServer | None = None


def set_server(server: IPCServer) -> None:
    """设置服务器实例"""
    global _server  # noqa: PLW0603
    _server = server


def get_server() -> IPCServer:
    """获取服务器实例"""
    if _server is None:
        msg = "Server not initialized"
        raise RuntimeError(msg)
    return _server


def _calculate_idle_time(last_used_at: datetime | None) -> int:
    """计算空闲时间（秒）"""
    if not last_used_at:
        return 0
    return int((datetime.now(UTC) - last_used_at).total_seconds())


@router.get("/sessions", response_model=RuntimeListResponse)
async def list_sessions(
    user: Annotated[UserContext, Depends(get_user_context)],
    *,
    all_users: Annotated[
        bool, Query(description="列出所有用户的会话（需要管理员权限）")
    ] = False,
) -> RuntimeListResponse:
    """列出运行时会话"""
    server = get_server()

    if all_users:
        sessions = await server.runtime_manager.list_sessions()
    else:
        sessions = await server.runtime_manager.list_sessions(user.user_id)

    return RuntimeListResponse(
        data=[
            RuntimeStatus(
                mcp_id=s.mcp_id,
                user_id=s.user_id,
                status=s.state.status,
                pid=s.state.pid,
                started_at=s.state.started_at,
                last_used_at=s.state.last_used_at,
                idle_time_sec=_calculate_idle_time(s.state.last_used_at),
                restart_count=s.state.restart_count,
                error_count=0,
                last_error=s.state.last_error,
            )
            for s in sessions
        ],
    )


@router.get("/sessions/{mcp_id}", response_model=RuntimeStatusResponse)
async def get_session_status(
    mcp_id: Annotated[str, PathParam(description="MCP Server ID")],
    user: Annotated[UserContext, Depends(get_user_context)],
) -> RuntimeStatusResponse:
    """获取特定会话状态"""
    server = get_server()

    session = await server.runtime_manager.get_session(user.user_id, mcp_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SESSION_NOT_FOUND",
                "message": f"No active session for server {mcp_id}",
            },
        )

    return RuntimeStatusResponse(
        data=RuntimeStatus(
            mcp_id=session.mcp_id,
            user_id=session.user_id,
            status=session.state.status,
            pid=session.state.pid,
            started_at=session.state.started_at,
            last_used_at=session.state.last_used_at,
            idle_time_sec=_calculate_idle_time(session.state.last_used_at),
            restart_count=session.state.restart_count,
            error_count=0,
            last_error=session.state.last_error,
        ),
    )
