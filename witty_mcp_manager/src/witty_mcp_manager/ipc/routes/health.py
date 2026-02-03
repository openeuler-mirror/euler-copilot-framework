"""健康检查路由"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from witty_mcp_manager import __version__
from witty_mcp_manager.ipc.schemas import HealthResponse, HealthStatus

if TYPE_CHECKING:
    from witty_mcp_manager.ipc.server import IPCServer

router = APIRouter(tags=["Health"])

# 服务器实例引用（在应用启动时设置）
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


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """健康检查"""
    server = get_server()
    sessions = await server.runtime_manager.list_sessions()
    return HealthResponse(
        data=HealthStatus(
            status="healthy",
            version=__version__,
            uptime_sec=server.uptime_sec,
            server_count=server.server_count,
            active_sessions=len([s for s in sessions if s.is_running]),
        ),
    )
