"""
UDS HTTP/JSON 服务器模块

提供完整的 Registry/Enable/Disable/Tools/Call API 接口。
"""

from __future__ import annotations

import asyncio
import logging
import stat
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from witty_mcp_manager import __version__
from witty_mcp_manager.adapters.http import StreamableHTTPAdapter
from witty_mcp_manager.adapters.sse import SSEAdapter
from witty_mcp_manager.adapters.stdio import STDIOAdapter
from witty_mcp_manager.diagnostics.preflight import PreflightChecker
from witty_mcp_manager.exceptions import ConfigError, WittyMCPError, WittyRuntimeError
from witty_mcp_manager.ipc.routes import (
    health_router,
    registry_router,
    runtime_router,
    tools_router,
)
from witty_mcp_manager.ipc.routes.health import set_server as set_health_server
from witty_mcp_manager.ipc.routes.registry import set_server as set_registry_server
from witty_mcp_manager.ipc.routes.runtime import set_server as set_runtime_server
from witty_mcp_manager.ipc.routes.tools import set_server as set_tools_server
from witty_mcp_manager.registry.models import ServerRecord, TransportType
from witty_mcp_manager.runtime.recycle import SessionRecycler

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from witty_mcp_manager.adapters.base import BaseAdapter
    from witty_mcp_manager.config.config import ManagerConfig
    from witty_mcp_manager.diagnostics.checker import Checker
    from witty_mcp_manager.overlay.resolver import OverlayResolver
    from witty_mcp_manager.overlay.storage import OverlayStorage
    from witty_mcp_manager.registry.discovery import Discovery
    from witty_mcp_manager.runtime.manager import RuntimeManager, Session

logger = logging.getLogger(__name__)


@dataclass
class IPCServerConfig:
    """IPC 服务器配置"""

    config: ManagerConfig
    discovery: Discovery
    checker: Checker
    overlay_storage: OverlayStorage
    overlay_resolver: OverlayResolver
    runtime_manager: RuntimeManager


class IPCServer:
    """
    UDS HTTP/JSON IPC 服务器

    管理 FastAPI 应用和 UDS socket 生命周期
    """

    DEFAULT_SOCKET_PATH = "/run/witty/mcp-manager.sock"
    DEFAULT_TCP_HOST = "127.0.0.1"
    DEFAULT_TCP_PORT = 8765

    def __init__(self, server_config: IPCServerConfig) -> None:
        """
        初始化 IPC 服务器

        Args:
            server_config: 服务器配置对象

        """
        self.config = server_config.config
        self.discovery = server_config.discovery
        self.checker = server_config.checker
        self.overlay_storage = server_config.overlay_storage
        self.overlay_resolver = server_config.overlay_resolver
        self.runtime_manager = server_config.runtime_manager

        # 服务器状态
        self._servers: dict[str, ServerRecord] = {}
        self._adapters: dict[str, BaseAdapter] = {}
        self._started_at: datetime | None = None
        self._shutdown_event = asyncio.Event()
        self._recycler: SessionRecycler | None = None

        # 创建 FastAPI 应用
        self.app = create_app(self)

    @property
    def server_count(self) -> int:
        """返回已注册的 Server 数量"""
        return len(self._servers)

    async def startup(self) -> None:
        """启动服务器初始化"""
        self._started_at = datetime.now(UTC)

        # 确保目录结构
        self.overlay_storage.ensure_directories()

        # 发现所有 MCP Servers
        servers = self.discovery.scan_all()
        self._servers = {s.id: s for s in servers}
        logger.info("Discovered %d MCP servers", len(self._servers))

        # 对每个 server 运行诊断
        preflight = PreflightChecker(self.config)
        for server in servers:
            diagnostics = self.checker.validate(server)
            server.diagnostics = diagnostics
            diagnostics = preflight.run_preflight(server)
            server.diagnostics = diagnostics
            if diagnostics.errors:
                logger.warning(
                    "Server %s has diagnostic errors: %s",
                    server.id,
                    diagnostics.errors,
                )

        # 启动会话回收器
        self._recycler = SessionRecycler(
            runtime_manager=self.runtime_manager,
            default_idle_ttl=self.config.idle_session_ttl,
        )
        await self._recycler.start()

    async def shutdown(self) -> None:
        """关闭服务器"""
        logger.info("Shutting down IPC server...")
        self._shutdown_event.set()

        if self._recycler:
            await self._recycler.stop()
            self._recycler = None

        # 关闭所有适配器
        for adapter in self._adapters.values():
            try:
                await adapter.disconnect()
            except Exception:
                logger.exception("Error disconnecting adapter")
        self._adapters.clear()

        # 关闭所有会话
        sessions = await self.runtime_manager.list_sessions()
        for session in sessions:
            try:
                await session.stop()
            except Exception:
                logger.exception("Error stopping session %s", session.session_key)

    def get_server(self, mcp_id: str) -> ServerRecord | None:
        """获取 Server 记录"""
        return self._servers.get(mcp_id)

    def list_servers(self) -> list[ServerRecord]:
        """列出所有 Server"""
        return list(self._servers.values())

    async def get_or_create_adapter(
        self,
        server: ServerRecord,
        session: Session,
    ) -> BaseAdapter:
        """
        获取或创建适配器

        Args:
            server: Server 记录
            session: 会话实例

        Returns:
            适配器实例

        """
        if session.state.status == "error":
            max_restarts = self.runtime_manager.MAX_RESTART_COUNT
            if session.state.restart_count >= max_restarts:
                msg = f"Session {session.session_key} exceeded max restart count ({max_restarts})"
                raise WittyRuntimeError(msg)
            await session.restart()

        # 使用 session_key 作为适配器的唯一标识（per user + per mcp_id）
        adapter_key = f"{session.user_id}:{server.id}"

        # 复用已有适配器
        if adapter_key in self._adapters:
            adapter = self._adapters[adapter_key]
            if adapter.is_connected:
                return adapter
            # 如果适配器存在但未连接，重新连接
            await adapter.connect(session)
            return adapter

        # 创建新适配器
        adapter = self._create_adapter(server, session.config)
        await adapter.connect(session)

        # 缓存适配器
        self._adapters[adapter_key] = adapter

        return adapter

    def _create_adapter(
        self,
        server: ServerRecord,
        config: Any,
    ) -> BaseAdapter:
        """创建适配器实例"""
        transport = server.default_config.transport

        if transport == TransportType.STDIO:
            return STDIOAdapter(server, config)
        if transport == TransportType.SSE:
            return SSEAdapter(server, config)
        if transport == TransportType.STREAMABLE_HTTP:
            return StreamableHTTPAdapter(server, config)

        msg = f"Unsupported transport: {transport}"
        raise ConfigError(msg)

    async def run_uds(self, socket_path: str | None = None) -> None:
        """
        以 UDS 模式运行服务器

        Args:
            socket_path: Socket 文件路径

        """
        path = socket_path or self.DEFAULT_SOCKET_PATH
        socket_file = Path(path)

        # 确保目录存在
        socket_file.parent.mkdir(parents=True, exist_ok=True)

        # 移除已存在的 socket 文件
        if socket_file.exists():
            socket_file.unlink()

        config = uvicorn.Config(
            app=self.app,
            uds=path,
            log_level="info",
        )
        uvicorn_server = uvicorn.Server(config)

        # 设置 socket 权限
        def _set_socket_permissions() -> None:
            socket_file.chmod(stat.S_IRUSR | stat.S_IWUSR)

        # 启动后设置权限
        original_startup = uvicorn_server.startup

        async def startup_with_permissions(*args: Any, **kwargs: Any) -> None:
            await original_startup(*args, **kwargs)
            _set_socket_permissions()

        uvicorn_server.startup = startup_with_permissions  # type: ignore[method-assign]

        logger.info("Starting UDS server at %s", path)
        await uvicorn_server.serve()

    async def run_tcp(
        self,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        """
        以 TCP 模式运行服务器（用于开发调试）

        Args:
            host: 绑定地址
            port: 绑定端口

        """
        config = uvicorn.Config(
            app=self.app,
            host=host or self.DEFAULT_TCP_HOST,
            port=port or self.DEFAULT_TCP_PORT,
            log_level="info",
        )
        uvicorn_server = uvicorn.Server(config)

        logger.info(
            "Starting TCP server at %s:%d",
            host or self.DEFAULT_TCP_HOST,
            port or self.DEFAULT_TCP_PORT,
        )
        await uvicorn_server.serve()

    @property
    def uptime_sec(self) -> int:
        """运行时间（秒）"""
        if not self._started_at:
            return 0
        return int((datetime.now(UTC) - self._started_at).total_seconds())


def create_app(server: IPCServer) -> FastAPI:
    """
    创建 FastAPI 应用

    Args:
        server: IPC 服务器实例

    Returns:
        FastAPI 应用实例

    """

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        """应用生命周期管理"""
        await server.startup()
        yield
        await server.shutdown()

    app = FastAPI(
        title="Witty MCP Manager",
        description="Universal MCP Host/Loader for Witty AI Assistant",
        version=__version__,
        lifespan=lifespan,
    )

    # 设置服务器实例到各路由模块
    set_health_server(server)
    set_registry_server(server)
    set_tools_server(server)
    set_runtime_server(server)

    # 注册路由
    app.include_router(health_router)
    app.include_router(registry_router)
    app.include_router(tools_router)
    app.include_router(runtime_router)

    # 注册异常处理器
    @app.exception_handler(WittyMCPError)
    async def witty_error_handler(_request: Any, exc: WittyMCPError) -> JSONResponse:
        """处理 Witty 异常"""
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {
                    "code": exc.__class__.__name__.upper(),
                    "message": str(exc),
                },
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Any, exc: HTTPException) -> JSONResponse:
        """处理 HTTP 异常"""
        detail = exc.detail
        error = detail if isinstance(detail, dict) else {"code": "HTTP_ERROR", "message": str(detail)}

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": error,
            },
        )

    return app


def create_app_for_docs() -> FastAPI:
    """
    创建仅用于文档生成的 FastAPI 应用（不需要实际服务器实例）

    Returns:
        FastAPI 应用实例

    """
    app = FastAPI(
        title="Witty MCP Manager API",
        description="""
# Witty MCP Manager API

通用 MCP Host/Loader，为 Witty AI 助手提供 MCP Server 管理能力。

## 核心功能

- **Registry API**: 列出/查询 MCP Server，支持启用/禁用
- **Tools API**: 发现 MCP Server 提供的工具
- **Tool Call API**: 调用 MCP Server 的工具
- **Configure API**: 用户级凭据配置（env/headers）
- **Runtime API**: 查询运行时会话状态
- **Health API**: 健康检查

## 身份认证

所有 API 需在请求头中携带 `X-Witty-User` 标识用户身份（仅本机 UDS 访问）。

## 传输方式

- **STDIO**: 子进程模式，使用 pipe 通信
- **SSE**: Server-Sent Events，连接远程服务
- **Streamable HTTP**: HTTP 流式传输（预留）

## 配置层级

- **系统层**: RPM 安装的默认配置（只读）
- **全局层**: 管理员通过 CLI 配置（影响所有用户）
- **用户层**: 用户通过 API 配置（仅影响自己）
        """,
        version=__version__,
        contact={
            "name": "openEuler SIG-Intelligence",
            "url": "https://atomgit.com/openeuler/euler-copilot-framework",
        },
        license_info={
            "name": "MulanPSL-2.0",
            "url": "https://license.coscl.org.cn/MulanPSL2",
        },
    )

    app.include_router(health_router)
    app.include_router(registry_router)
    app.include_router(tools_router)
    app.include_router(runtime_router)

    return app
