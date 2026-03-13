"""IPC routes 补充测试

补充 tools、registry、runtime、health 路由中未覆盖的分支和边界条件。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from witty_mcp_manager.ipc.auth import HEADER_USER_ID, UserContext
from witty_mcp_manager.ipc.routes.registry import (
    _apply_configure_request,
    _build_configure_result,
    _validate_configure_request,
)
from witty_mcp_manager.ipc.routes.tools import _ensure_server_ready, _get_cache_info
from witty_mcp_manager.ipc.schemas import ConfigureRequest
from witty_mcp_manager.registry.models import Diagnostics, Override, TransportType

# =============================================================================
# Registry 路由辅助函数补充测试
# =============================================================================


class TestDetermineServerStatusEdgeCases:
    """_determine_server_status 边界条件"""

    def test_command_not_allowed_no_stdio(self) -> None:
        """测试命令不允许但无 STDIO 配置"""
        from witty_mcp_manager.ipc.routes.registry import _determine_server_status

        server = MagicMock()
        server.diagnostics = MagicMock()
        server.diagnostics.command_allowed = False
        server.diagnostics.errors = []
        server.default_config = MagicMock()
        server.default_config.stdio = None

        status, reason = _determine_server_status(server)
        assert status == "unavailable"
        assert "白名单" in reason  # type: ignore[operator]

    def test_with_errors(self) -> None:
        """测试有错误时返回 unavailable"""
        from witty_mcp_manager.ipc.routes.registry import _determine_server_status

        server = MagicMock()
        server.diagnostics = MagicMock()
        server.diagnostics.command_allowed = True
        server.diagnostics.errors = ["Missing file"]
        server.diagnostics.deps_missing = {}

        status, reason = _determine_server_status(server)
        assert status == "unavailable"
        assert reason == "Missing file"

    def test_with_python_deps_missing(self) -> None:
        """测试 Python 依赖缺失"""
        from witty_mcp_manager.ipc.routes.registry import _determine_server_status

        server = MagicMock()
        server.diagnostics = MagicMock()
        server.diagnostics.command_allowed = True
        server.diagnostics.errors = []
        server.diagnostics.deps_missing = {"python": ["requests"]}

        status, reason = _determine_server_status(server)
        assert status == "degraded"
        assert "Python" in reason  # type: ignore[operator]

    def test_no_missing_deps(self) -> None:
        """测试无缺失依赖时 ready"""
        from witty_mcp_manager.ipc.routes.registry import _determine_server_status

        server = MagicMock()
        server.diagnostics = MagicMock()
        server.diagnostics.command_allowed = True
        server.diagnostics.errors = []
        server.diagnostics.deps_missing = {"system": [], "python": []}
        server.diagnostics.sse_reachable = None

        status, reason = _determine_server_status(server)
        assert status == "ready"
        assert reason is None

    def test_sse_backend_unreachable(self) -> None:
        """SSE 后端不可达时返回 unavailable"""
        from witty_mcp_manager.ipc.routes.registry import _determine_server_status

        server = MagicMock()
        server.diagnostics = MagicMock()
        server.diagnostics.command_allowed = True
        server.diagnostics.errors = []
        server.diagnostics.deps_missing = {}
        server.diagnostics.sse_reachable = False
        server.default_config.sse = MagicMock()
        server.default_config.sse.url = "http://127.0.0.1:19999/sse"

        status, reason = _determine_server_status(server)
        assert status == "unavailable"
        assert "19999" in (reason or "")

    def test_sse_backend_reachable(self) -> None:
        """SSE 后端可达时返回 ready"""
        from witty_mcp_manager.ipc.routes.registry import _determine_server_status

        server = MagicMock()
        server.diagnostics = MagicMock()
        server.diagnostics.command_allowed = True
        server.diagnostics.errors = []
        server.diagnostics.deps_missing = {}
        server.diagnostics.sse_reachable = True

        status, reason = _determine_server_status(server)
        assert status == "ready"
        assert reason is None


class TestValidateConfigureRequest:
    """_validate_configure_request 测试"""

    def test_env_only_for_stdio(self) -> None:
        """测试 env 仅支持 STDIO"""
        request = ConfigureRequest(env={"KEY": "val"})
        # STDIO 应通过
        _validate_configure_request(TransportType.STDIO, request)

    def test_env_rejected_for_sse(self) -> None:
        """测试 SSE 不支持 env"""
        request = ConfigureRequest(env={"KEY": "val"})
        with pytest.raises(HTTPException) as exc_info:
            _validate_configure_request(TransportType.SSE, request)
        assert exc_info.value.status_code == 400
        assert "INVALID_ENV" in str(exc_info.value.detail)

    def test_headers_only_for_sse(self) -> None:
        """测试 headers 仅支持 SSE/HTTP"""
        request = ConfigureRequest(headers={"Authorization": "Bearer tok"})
        # SSE 应通过
        _validate_configure_request(TransportType.SSE, request)

    def test_headers_rejected_for_stdio(self) -> None:
        """测试 STDIO 不支持 headers"""
        request = ConfigureRequest(headers={"X-Key": "val"})
        with pytest.raises(HTTPException) as exc_info:
            _validate_configure_request(TransportType.STDIO, request)
        assert exc_info.value.status_code == 400
        assert "INVALID_HEADERS" in str(exc_info.value.detail)


class TestApplyConfigureRequest:
    """_apply_configure_request 测试"""

    def _make_secrets(self) -> MagicMock:
        """构造一个简单的 SecretsManager mock"""
        secrets = MagicMock()
        secrets.save_secret = MagicMock(return_value=None)
        return secrets

    def test_apply_env_stores_secret_refs(self) -> None:
        """env 明文应被存入 SecretsManager，override 中保存 ${secrets:...} 引用"""
        override = Override(scope="user/alice")
        plaintext = "MY_PLAINTEXT_VALUE_xyz987"
        request = ConfigureRequest(env={"API_KEY": plaintext})
        secrets = self._make_secrets()
        _apply_configure_request(override, request, secrets, "alice", "git_mcp")
        # SecretsManager.save_secret 应被调用，第二个参数是明文值
        assert secrets.save_secret.called
        call_args = secrets.save_secret.call_args
        assert call_args[0][1] == plaintext
        # override.env 应存储 ${secrets:...} 引用，而非明文
        ref = override.env.get("API_KEY", "")
        assert ref.startswith("${secrets:")
        assert plaintext not in ref  # 明文值不出现在引用中

    def test_apply_headers_stores_secret_refs(self) -> None:
        """headers 明文应被存入 SecretsManager，override 中保存 ${secrets:...} 引用"""
        override = Override(scope="user/alice")
        plaintext = "Bearer MY_TOKEN_abc123"
        request = ConfigureRequest(headers={"Authorization": plaintext})
        secrets = self._make_secrets()
        _apply_configure_request(override, request, secrets, "alice", "sse_mcp")
        ref = override.headers.get("Authorization", "")
        assert ref.startswith("${secrets:")
        assert plaintext not in ref

    def test_apply_none_fields_unchanged(self) -> None:
        """测试 None 字段不修改"""
        override = Override(scope="user/alice", env={"EXISTING": "val"})
        request = ConfigureRequest()  # env=None, headers=None
        secrets = self._make_secrets()
        _apply_configure_request(override, request, secrets, "alice", "git_mcp")
        assert override.env == {"EXISTING": "val"}
        secrets.save_secret.assert_not_called()

    def test_secret_key_sanitizes_special_chars(self) -> None:
        """user_id、mcp_id 或 key 中的特殊字符应被替换为安全字符"""
        from witty_mcp_manager.ipc.routes.registry import _make_secret_key

        key = _make_secret_key("user@example.com", "my-mcp/v2", "env", "KEY.NAME")
        # 不包含 @、/、. 等字符
        assert "@" not in key
        assert "/" not in key
        assert "." not in key


class TestBuildConfigureResult:
    """_build_configure_result 测试"""

    def test_secret_refs_masked_in_response(self) -> None:
        """${secrets:...} 引用在响应中应被替换为 secret://***"""
        override = Override(
            scope="user/alice",
            env={"API_KEY": "${secrets:alice__git_mcp__env__API_KEY}"},
            headers={"Authorization": "${secrets:alice__git_mcp__hdr__Authorization}"},
        )
        result = _build_configure_result("git_mcp", override)
        assert result.mcp_id == "git_mcp"
        assert result.env["API_KEY"] == "secret://***"
        assert result.headers["Authorization"] == "secret://***"
        assert result.updated_at is not None

    def test_non_secret_values_pass_through(self) -> None:
        """非 ${secrets:...} 值应原样返回"""
        override = Override(
            scope="user/alice",
            env={"MODE": "debug"},
            headers={},
        )
        result = _build_configure_result("git_mcp", override)
        assert result.env["MODE"] == "debug"

    def test_empty_dicts(self) -> None:
        """空 env/headers 不报错"""
        override = Override(scope="user/alice")
        result = _build_configure_result("git_mcp", override)
        assert result.env == {}
        assert result.headers == {}


# =============================================================================
# Tools 路由辅助函数测试
# =============================================================================


class TestEnsureServerReady:
    """_ensure_server_ready 测试"""

    def test_no_diagnostics_passes(self) -> None:
        """测试无诊断信息时通过"""
        server = MagicMock()
        server.diagnostics = None
        _ensure_server_ready(server)  # 不抛异常

    def test_command_not_allowed(self) -> None:
        """测试命令不允许"""
        server = MagicMock()
        server.diagnostics = MagicMock()
        server.diagnostics.command_allowed = False
        with pytest.raises(HTTPException) as exc_info:
            _ensure_server_ready(server)
        assert exc_info.value.status_code == 403

    def test_command_not_found(self) -> None:
        """测试命令不存在"""
        server = MagicMock()
        server.diagnostics = MagicMock()
        server.diagnostics.command_allowed = True
        server.diagnostics.command_exists = False
        with pytest.raises(HTTPException) as exc_info:
            _ensure_server_ready(server)
        assert exc_info.value.status_code == 503

    def test_config_invalid(self) -> None:
        """测试配置无效"""
        server = MagicMock()
        server.diagnostics = MagicMock()
        server.diagnostics.command_allowed = True
        server.diagnostics.command_exists = True
        server.diagnostics.config_valid = False
        server.diagnostics.errors = ["bad config"]
        with pytest.raises(HTTPException) as exc_info:
            _ensure_server_ready(server)
        assert exc_info.value.status_code == 400

    def test_all_ok_passes(self) -> None:
        """测试全部正常时通过"""
        server = MagicMock()
        server.diagnostics = MagicMock()
        server.diagnostics.command_allowed = True
        server.diagnostics.command_exists = True
        server.diagnostics.config_valid = True
        _ensure_server_ready(server)  # 不抛异常


class TestGetCacheInfo:
    """_get_cache_info 测试"""

    def test_no_cache(self) -> None:
        """测试无缓存"""
        from witty_mcp_manager.adapters.base import GLOBAL_TOOLS_CACHE

        adapter = MagicMock()
        adapter.mcp_id = "test_mcp"
        adapter.get_cache_ttl = MagicMock(return_value=600)

        # 确保全局缓存为空
        if "test_mcp" in GLOBAL_TOOLS_CACHE:
            del GLOBAL_TOOLS_CACHE["test_mcp"]

        result = _get_cache_info(adapter, force_refresh=False)
        assert result is None

    def test_with_cache(self) -> None:
        """测试有缓存"""
        import asyncio

        from witty_mcp_manager.adapters.base import GLOBAL_TOOLS_CACHE, Tool

        adapter = MagicMock()
        adapter.mcp_id = "test_mcp_cached"
        adapter.get_cache_ttl = MagicMock(return_value=600)

        # 设置全局缓存
        tools = [Tool(name="tool1")]
        cached_at = datetime.now(UTC)
        GLOBAL_TOOLS_CACHE["test_mcp_cached"] = (tools, cached_at, asyncio.Lock())

        result = _get_cache_info(adapter, force_refresh=False)
        assert result is not None
        assert result.from_cache is True

        # 清理
        del GLOBAL_TOOLS_CACHE["test_mcp_cached"]

    def test_forced_refresh_no_cache(self) -> None:
        """测试强制刷新时 from_cache=False"""
        import asyncio

        from witty_mcp_manager.adapters.base import GLOBAL_TOOLS_CACHE, Tool

        adapter = MagicMock()
        adapter.mcp_id = "test_mcp_refresh"
        adapter.get_cache_ttl = MagicMock(return_value=600)

        # 设置全局缓存
        tools = [Tool(name="tool1")]
        cached_at = datetime.now(UTC)
        GLOBAL_TOOLS_CACHE["test_mcp_refresh"] = (tools, cached_at, asyncio.Lock())

        result = _get_cache_info(adapter, force_refresh=True)
        assert result is not None
        assert result.from_cache is False

        # 清理
        del GLOBAL_TOOLS_CACHE["test_mcp_refresh"]


# =============================================================================
# IPC Server 补充集成测试
# =============================================================================


class TestIPCServerConfigureEndpoint:
    """configure 接口集成测试"""

    @pytest.fixture
    def mock_deps(self) -> dict[str, Any]:
        """创建模拟依赖"""
        from witty_mcp_manager.config.config import ManagerConfig
        from witty_mcp_manager.diagnostics.checker import Checker
        from witty_mcp_manager.overlay.resolver import EffectiveConfig, OverlayResolver
        from witty_mcp_manager.overlay.storage import OverlayStorage
        from witty_mcp_manager.registry.discovery import Discovery
        from witty_mcp_manager.registry.models import (
            Concurrency,
            Diagnostics,
            NormalizedConfig,
            ServerRecord,
            SourceType,
            StdioConfig,
            Timeouts,
            TransportType,
        )
        from witty_mcp_manager.runtime.manager import RuntimeManager

        config = MagicMock(spec=ManagerConfig)
        config.scan_paths = []
        config.admin_sources = []
        config.idle_session_ttl = 600

        discovery = MagicMock(spec=Discovery)

        test_server = ServerRecord(
            id="test_mcp",
            name="Test MCP",
            summary="Test",
            source=SourceType.RPM,
            install_root="/opt/test",
            upstream_key="test_mcp",
            transport=TransportType.STDIO,
            default_config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="uv", args=["run"]),
            ),
            diagnostics=Diagnostics(),
        )
        discovery.scan_all.return_value = [test_server]

        checker = MagicMock(spec=Checker)
        checker.validate.return_value = Diagnostics()

        overlay_storage = MagicMock(spec=OverlayStorage)
        overlay_storage.load_override.return_value = None
        overlay_storage.ensure_directories.return_value = None

        overlay_resolver = MagicMock(spec=OverlayResolver)
        overlay_resolver.resolve.return_value = EffectiveConfig(
            mcp_id="test_mcp",
            user_id="user123",
            disabled=False,
            config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="uv", args=["run"]),
            ),
            timeouts=Timeouts(),
            concurrency=Concurrency(),
        )
        # SecretsManager mock：configure 路由需要 overlay_resolver.secrets
        overlay_resolver.secrets = MagicMock()
        overlay_resolver.secrets.save_secret = MagicMock(return_value=None)

        runtime_manager = MagicMock(spec=RuntimeManager)
        runtime_manager.list_sessions = AsyncMock(return_value=[])
        runtime_manager.get_session = AsyncMock(return_value=None)

        return {
            "config": config,
            "discovery": discovery,
            "checker": checker,
            "overlay_storage": overlay_storage,
            "overlay_resolver": overlay_resolver,
            "runtime_manager": runtime_manager,
            "test_server": test_server,
        }

    @pytest.fixture
    def test_client(self, mock_deps: dict[str, Any]) -> TestClient:
        """创建测试客户端"""
        from witty_mcp_manager.ipc.server import IPCServer, IPCServerConfig

        server_config = IPCServerConfig(
            config=mock_deps["config"],
            discovery=mock_deps["discovery"],
            checker=mock_deps["checker"],
            overlay_storage=mock_deps["overlay_storage"],
            overlay_resolver=mock_deps["overlay_resolver"],
            runtime_manager=mock_deps["runtime_manager"],
        )
        server = IPCServer(server_config)
        server._servers = {mock_deps["test_server"].id: mock_deps["test_server"]}  # noqa: SLF001
        server._started_at = datetime.now(UTC)  # noqa: SLF001
        return TestClient(server.app)

    def test_get_server_detail(
        self,
        test_client: TestClient,
        mock_deps: dict[str, Any],
    ) -> None:
        """测试获取 server 详情"""
        response = test_client.get(
            "/v1/servers/test_mcp",
            headers={HEADER_USER_ID: "user123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"]
        assert data["data"]["mcp_id"] == "test_mcp"

    def test_disable_nonexistent_server(self, test_client: TestClient) -> None:
        """测试禁用不存在的 server"""
        response = test_client.post(
            "/v1/me/servers/nonexistent/disable",
            headers={HEADER_USER_ID: "user123"},
        )
        assert response.status_code == 404

    def test_configure_nonexistent_server(self, test_client: TestClient) -> None:
        """测试配置不存在的 server"""
        response = test_client.post(
            "/v1/me/servers/nonexistent/configure",
            headers={HEADER_USER_ID: "user123"},
            json={"env": {"KEY": "val"}},
        )
        assert response.status_code == 404

    def test_configure_env(
        self,
        test_client: TestClient,
        mock_deps: dict[str, Any],
    ) -> None:
        """测试配置 env：明文不回显，返回 secret://*** 引用"""
        response = test_client.post(
            "/v1/me/servers/test_mcp/configure",
            headers={HEADER_USER_ID: "user123"},
            json={"env": {"API_KEY": "my_plaintext_token"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"]
        # 明文不应出现在响应中
        env = data["data"]["env"]
        assert env.get("API_KEY") == "secret://***"
        assert "my_plaintext_token" not in str(data)
        # SecretsManager.save_secret 应被调用
        mock_deps["overlay_resolver"].secrets.save_secret.assert_called()
        mock_deps["overlay_storage"].save_override.assert_called()

    def test_list_servers_with_disabled(
        self,
        test_client: TestClient,
        mock_deps: dict[str, Any],
    ) -> None:
        """测试列表包含禁用 server"""
        response = test_client.get(
            "/v1/servers?include_disabled=true",
            headers={HEADER_USER_ID: "user123"},
        )
        assert response.status_code == 200


# =============================================================================
# IPCServer 类测试
# =============================================================================


class TestIPCServerClass:
    """IPCServer 类方法测试"""

    def test_server_count(self) -> None:
        """测试 server_count 属性"""
        from witty_mcp_manager.ipc.server import IPCServer, IPCServerConfig

        config = MagicMock()
        config.scan_paths = []
        config.admin_sources = []

        server_config = IPCServerConfig(
            config=config,
            discovery=MagicMock(),
            checker=MagicMock(),
            overlay_storage=MagicMock(),
            overlay_resolver=MagicMock(),
            runtime_manager=MagicMock(),
        )
        server = IPCServer(server_config)
        assert server.server_count == 0

    def test_get_server_none(self) -> None:
        """测试获取不存在的 server"""
        from witty_mcp_manager.ipc.server import IPCServer, IPCServerConfig

        server_config = IPCServerConfig(
            config=MagicMock(),
            discovery=MagicMock(),
            checker=MagicMock(),
            overlay_storage=MagicMock(),
            overlay_resolver=MagicMock(),
            runtime_manager=MagicMock(),
        )
        server = IPCServer(server_config)
        assert server.get_server("nonexistent") is None

    def test_list_servers_empty(self) -> None:
        """测试空列表"""
        from witty_mcp_manager.ipc.server import IPCServer, IPCServerConfig

        server_config = IPCServerConfig(
            config=MagicMock(),
            discovery=MagicMock(),
            checker=MagicMock(),
            overlay_storage=MagicMock(),
            overlay_resolver=MagicMock(),
            runtime_manager=MagicMock(),
        )
        server = IPCServer(server_config)
        assert server.list_servers() == []

    def test_uptime_sec_not_started(self) -> None:
        """测试未启动时运行时间为 0"""
        from witty_mcp_manager.ipc.server import IPCServer, IPCServerConfig

        server_config = IPCServerConfig(
            config=MagicMock(),
            discovery=MagicMock(),
            checker=MagicMock(),
            overlay_storage=MagicMock(),
            overlay_resolver=MagicMock(),
            runtime_manager=MagicMock(),
        )
        server = IPCServer(server_config)
        assert server.uptime_sec == 0

    def test_create_adapter_unsupported_transport(self) -> None:
        """测试不支持的传输类型"""
        from witty_mcp_manager.ipc.server import IPCServer, IPCServerConfig
        from witty_mcp_manager.registry.models import TransportType

        server_config = IPCServerConfig(
            config=MagicMock(),
            discovery=MagicMock(),
            checker=MagicMock(),
            overlay_storage=MagicMock(),
            overlay_resolver=MagicMock(),
            runtime_manager=MagicMock(),
        )
        ipc_server = IPCServer(server_config)

        # 创建 mock server 使用 STREAMABLE_HTTP
        mock_srv = MagicMock()
        mock_srv.default_config.transport = TransportType.STREAMABLE_HTTP

        # StreamableHTTPAdapter 应被创建
        adapter = ipc_server._create_adapter(mock_srv, MagicMock())  # noqa: SLF001
        assert adapter is not None

    def test_refresh_server_reachability_updates_diagnostics(self) -> None:
        """刷新可达性时应更新诊断状态"""
        from witty_mcp_manager.ipc.server import IPCServer, IPCServerConfig
        from witty_mcp_manager.registry.models import NormalizedConfig, ServerRecord, SourceType, SseConfig

        checker = MagicMock()
        checker.check_sse_reachable.return_value = True

        server_config = IPCServerConfig(
            config=MagicMock(),
            discovery=MagicMock(),
            checker=checker,
            overlay_storage=MagicMock(),
            overlay_resolver=MagicMock(),
            runtime_manager=MagicMock(),
        )
        ipc_server = IPCServer(server_config)

        srv = ServerRecord(
            id="test_sse",
            name="Test SSE",
            summary="",
            source=SourceType.ADMIN,
            install_root="/tmp/test_sse",
            upstream_key="test_sse",
            transport=TransportType.SSE,
            default_config=NormalizedConfig(
                transport=TransportType.SSE,
                sse=SseConfig(url="http://127.0.0.1:12555/sse"),
            ),
            diagnostics=Diagnostics(sse_reachable=False),
        )

        ipc_server.refresh_server_reachability(srv)

        checker.check_sse_reachable.assert_called_once_with(srv, log_failure=False)
        assert srv.diagnostics.sse_reachable is True


class TestRegistryRoutesRefreshReachability:
    """Registry 路由应在返回状态前刷新 SSE 可达性"""

    @pytest.mark.asyncio
    async def test_list_servers_refreshes_reachability(self) -> None:
        from witty_mcp_manager.ipc.routes import registry as registry_routes

        srv = MagicMock()
        srv.id = "test_sse"
        srv.name = "Test SSE"
        srv.summary = ""
        srv.source.value = "admin"
        srv.diagnostics.command_allowed = True
        srv.diagnostics.errors = []
        srv.diagnostics.deps_missing = {}
        srv.diagnostics.sse_reachable = None

        server = MagicMock()
        server.list_servers.return_value = [srv]
        server.refresh_server_reachability = MagicMock()
        server.overlay_resolver.resolve.return_value = MagicMock(disabled=False)
        server.overlay_storage.load_override.return_value = None

        registry_routes.set_server(server)

        user = UserContext(user_id="alice")
        await registry_routes.list_servers(user, include_disabled=False)

        server.refresh_server_reachability.assert_called_once_with(srv)

    @pytest.mark.asyncio
    async def test_get_server_detail_refreshes_reachability(self) -> None:
        from witty_mcp_manager.ipc.routes import registry as registry_routes

        diagnostics = Diagnostics()
        srv = MagicMock()
        srv.id = "test_sse"
        srv.name = "Test SSE"
        srv.summary = ""
        srv.source.value = "admin"
        srv.default_config.transport.value = "sse"
        srv.default_config.stdio = None
        srv.default_config.sse = MagicMock(url="http://127.0.0.1:12555/sse")
        srv.install_root = "/tmp/test_sse"
        srv.upstream_key = "test_sse"
        srv.diagnostics = diagnostics

        effective = MagicMock()
        effective.disabled = False
        effective.config.transport.value = "sse"
        effective.timeouts.tool_call = 30
        effective.timeouts.idle_ttl = 600
        effective.concurrency.max_per_user = 5
        effective.env = {}

        server = MagicMock()
        server.get_server.return_value = srv
        server.refresh_server_reachability = MagicMock()
        server.overlay_resolver.resolve.return_value = effective

        registry_routes.set_server(server)

        user = UserContext(user_id="alice")
        await registry_routes.get_server_detail("test_sse", user)

        server.refresh_server_reachability.assert_called_once_with(srv)
