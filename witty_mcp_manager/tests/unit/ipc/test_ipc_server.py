"""IPCServer 补充单元测试

覆盖 ipc/server.py 中的 startup/shutdown/adapter 管理逻辑。
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from witty_mcp_manager.exceptions import ConfigError, WittyRuntimeError
from witty_mcp_manager.ipc.server import IPCServer, IPCServerConfig, create_app
from witty_mcp_manager.registry.models import TransportType


@pytest.fixture
def server_config() -> IPCServerConfig:
    """创建 IPCServerConfig 实例"""
    config = MagicMock()
    config.scan_paths = []
    config.admin_sources = []
    config.idle_session_ttl = 600

    return IPCServerConfig(
        config=config,
        discovery=MagicMock(),
        checker=MagicMock(),
        overlay_storage=MagicMock(),
        overlay_resolver=MagicMock(),
        runtime_manager=MagicMock(),
    )


@pytest.fixture
def ipc_server(server_config: IPCServerConfig) -> IPCServer:
    """创建 IPCServer 实例"""
    return IPCServer(server_config)


class TestIPCServerStartup:
    """IPCServer startup 测试"""

    @pytest.mark.asyncio
    async def test_startup_discovers_servers(self, ipc_server: IPCServer) -> None:
        """测试 startup 发现所有 server"""
        mock_server = MagicMock()
        mock_server.id = "test-server"
        mock_server.diagnostics = MagicMock()
        mock_server.diagnostics.errors = []
        ipc_server.discovery.scan_all.return_value = [mock_server]  # type: ignore[attr-defined]
        ipc_server.checker.validate.return_value = MagicMock(errors=[])  # type: ignore[attr-defined]

        await ipc_server.startup()

        assert ipc_server.server_count == 1
        assert ipc_server._started_at is not None  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_startup_runs_diagnostics(self, ipc_server: IPCServer) -> None:
        """测试 startup 运行诊断"""
        mock_server = MagicMock()
        mock_server.id = "diag-server"
        diag = MagicMock()
        diag.errors = ["some error"]
        ipc_server.discovery.scan_all.return_value = [mock_server]  # type: ignore[attr-defined]
        ipc_server.checker.validate.return_value = diag  # type: ignore[attr-defined]

        await ipc_server.startup()

        ipc_server.checker.validate.assert_called_once_with(mock_server)  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_startup_starts_recycler(self, ipc_server: IPCServer) -> None:
        """测试 startup 启动回收器"""
        ipc_server.discovery.scan_all.return_value = []  # type: ignore[attr-defined]
        await ipc_server.startup()

        assert ipc_server._recycler is not None  # noqa: SLF001


class TestIPCServerShutdown:
    """IPCServer shutdown 测试"""

    @pytest.mark.asyncio
    async def test_shutdown_stops_recycler(self, ipc_server: IPCServer) -> None:
        """测试 shutdown 停止回收器"""
        mock_recycler = AsyncMock()
        ipc_server._recycler = mock_recycler  # noqa: SLF001
        ipc_server.runtime_manager.list_sessions = AsyncMock(return_value=[])  # type: ignore[method-assign]

        await ipc_server.shutdown()

        mock_recycler.stop.assert_awaited_once()
        assert ipc_server._recycler is None  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_shutdown_disconnects_adapters(self, ipc_server: IPCServer) -> None:
        """测试 shutdown 断开所有适配器"""
        mock_adapter = AsyncMock()
        ipc_server._adapters["key1"] = mock_adapter  # noqa: SLF001
        ipc_server.runtime_manager.list_sessions = AsyncMock(return_value=[])  # type: ignore[method-assign]

        await ipc_server.shutdown()

        mock_adapter.disconnect.assert_awaited_once()
        assert len(ipc_server._adapters) == 0  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_shutdown_handles_adapter_disconnect_error(self, ipc_server: IPCServer) -> None:
        """测试 shutdown 处理适配器断开错误"""
        mock_adapter = AsyncMock()
        mock_adapter.disconnect.side_effect = RuntimeError("disconnect failed")
        ipc_server._adapters["key1"] = mock_adapter  # noqa: SLF001
        ipc_server.runtime_manager.list_sessions = AsyncMock(return_value=[])  # type: ignore[method-assign]

        # 不应抛出异常
        await ipc_server.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_stops_sessions(self, ipc_server: IPCServer) -> None:
        """测试 shutdown 停止所有会话"""
        mock_session = AsyncMock()
        mock_session.session_key = "s1"
        ipc_server.runtime_manager.list_sessions = AsyncMock(return_value=[mock_session])  # type: ignore[method-assign]

        await ipc_server.shutdown()

        mock_session.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_handles_session_stop_error(self, ipc_server: IPCServer) -> None:
        """测试 shutdown 处理会话停止错误"""
        mock_session = AsyncMock()
        mock_session.session_key = "s1"
        mock_session.stop.side_effect = RuntimeError("stop failed")
        ipc_server.runtime_manager.list_sessions = AsyncMock(return_value=[mock_session])  # type: ignore[method-assign]

        # 不应抛出异常
        await ipc_server.shutdown()


class TestIPCServerAdapters:
    """IPCServer 适配器管理测试"""

    def test_create_adapter_stdio(self, ipc_server: IPCServer) -> None:
        """测试创建 STDIO 适配器"""
        mock_server = MagicMock()
        mock_server.default_config.transport = TransportType.STDIO
        mock_config = MagicMock()

        adapter = ipc_server._create_adapter(mock_server, mock_config)  # noqa: SLF001
        assert adapter is not None

    def test_create_adapter_sse(self, ipc_server: IPCServer) -> None:
        """测试创建 SSE 适配器"""
        mock_server = MagicMock()
        mock_server.default_config.transport = TransportType.SSE
        mock_config = MagicMock()

        adapter = ipc_server._create_adapter(mock_server, mock_config)  # noqa: SLF001
        assert adapter is not None

    def test_create_adapter_streamable_http(self, ipc_server: IPCServer) -> None:
        """测试创建 StreamableHTTP 适配器"""
        mock_server = MagicMock()
        mock_server.default_config.transport = TransportType.STREAMABLE_HTTP
        mock_config = MagicMock()

        adapter = ipc_server._create_adapter(mock_server, mock_config)  # noqa: SLF001
        assert adapter is not None

    def test_create_adapter_unsupported_raises(self, ipc_server: IPCServer) -> None:
        """测试不支持的传输类型抛出 ConfigError"""
        mock_server = MagicMock()
        mock_server.default_config.transport = "unknown_transport"
        mock_config = MagicMock()

        with pytest.raises(ConfigError, match="Unsupported transport"):
            ipc_server._create_adapter(mock_server, mock_config)  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_get_or_create_adapter_new(self, ipc_server: IPCServer) -> None:
        """测试首次获取适配器会创建新实例"""
        mock_server = MagicMock()
        mock_server.default_config.transport = TransportType.STDIO

        mock_session = MagicMock()
        mock_session.session_key = "user:test_mcp"
        mock_session.state.status = "running"
        mock_session.config = MagicMock()

        mock_adapter = AsyncMock()
        mock_adapter.is_connected = False

        with patch.object(ipc_server, "_create_adapter", return_value=mock_adapter):
            adapter = await ipc_server.get_or_create_adapter(mock_server, mock_session)
            mock_adapter.connect.assert_awaited_once_with(mock_session)
            assert adapter is mock_adapter

    @pytest.mark.asyncio
    async def test_get_or_create_adapter_cached(self, ipc_server: IPCServer) -> None:
        """测试已缓存适配器直接返回"""
        mock_adapter = AsyncMock()
        mock_adapter.is_connected = True

        mock_server = MagicMock()
        mock_server.id = "test_mcp"
        mock_server.default_config.transport = TransportType.STDIO

        mock_session = MagicMock()
        mock_session.user_id = "user"
        mock_session.session_key = "user:test_mcp"
        mock_session.state.status = "running"

        ipc_server._adapters["user:test_mcp"] = mock_adapter  # noqa: SLF001

        adapter = await ipc_server.get_or_create_adapter(mock_server, mock_session)
        assert adapter is mock_adapter
        mock_adapter.connect.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_or_create_adapter_error_state_restart(self, ipc_server: IPCServer) -> None:
        """测试 error 状态下重启会话"""
        mock_session = AsyncMock()
        mock_session.session_key = "user:mcp"
        mock_session.state.status = "error"
        mock_session.state.restart_count = 0
        mock_session.config = MagicMock()

        ipc_server.runtime_manager.MAX_RESTART_COUNT = 3

        mock_adapter = AsyncMock()
        mock_adapter.is_connected = False

        with patch.object(ipc_server, "_create_adapter", return_value=mock_adapter):
            await ipc_server.get_or_create_adapter(MagicMock(), mock_session)
            mock_session.restart.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_or_create_adapter_max_restart_exceeded(self, ipc_server: IPCServer) -> None:
        """测试超过最大重启次数抛出异常"""
        mock_session = MagicMock()
        mock_session.session_key = "user:mcp"
        mock_session.state.status = "error"
        mock_session.state.restart_count = 5

        ipc_server.runtime_manager.MAX_RESTART_COUNT = 3

        with pytest.raises(WittyRuntimeError, match="exceeded max restart count"):
            await ipc_server.get_or_create_adapter(MagicMock(), mock_session)


class TestIPCServerProperties:
    """IPCServer 属性测试"""

    def test_uptime_sec_after_start(self, ipc_server: IPCServer) -> None:
        """测试启动后运行时间"""
        ipc_server._started_at = datetime.now(UTC)  # noqa: SLF001
        assert ipc_server.uptime_sec >= 0

    def test_list_servers(self, ipc_server: IPCServer) -> None:
        """测试列出服务器"""
        s1 = MagicMock()
        s1.id = "s1"
        s2 = MagicMock()
        s2.id = "s2"
        ipc_server._servers = {"s1": s1, "s2": s2}  # noqa: SLF001

        servers = ipc_server.list_servers()
        assert len(servers) == 2


class TestCreateApp:
    """create_app 测试"""

    def test_app_has_routers(self, ipc_server: IPCServer) -> None:
        """测试应用包含路由"""
        app = create_app(ipc_server)
        routes = [r.path for r in app.routes]  # type: ignore[attr-defined]
        assert any("/v1" in r for r in routes)
