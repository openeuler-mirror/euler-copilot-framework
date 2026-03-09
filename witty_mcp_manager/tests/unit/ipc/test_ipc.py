"""
IPC 模块单元测试
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from witty_mcp_manager.ipc.auth import (
    HEADER_USER_ID,
    SYSTEM_USER_ID,
    UserContext,
    _is_valid_user_id,
    create_system_context,
    get_user_context,
)
from witty_mcp_manager.ipc.schemas import (
    APIResponse,
    CacheInfo,
    ContentItem,
    HealthStatus,
    RuntimeStatus,
    ServerSummary,
    ToolCallRequest,
    ToolCallResult,
    ToolSchema,
)

# =============================================================================
# Auth 模块测试
# =============================================================================


class TestUserContext:
    """UserContext 测试"""

    def test_basic_creation(self) -> None:
        """测试基本创建"""
        ctx = UserContext(user_id="user123")
        assert ctx.user_id == "user123"
        assert ctx.session_id is None
        assert ctx.request_id is None
        assert not ctx.is_system

    def test_with_session(self) -> None:
        """测试带会话 ID"""
        ctx = UserContext(user_id="user123", session_id="sess456")
        assert ctx.user_id == "user123"
        assert ctx.session_id == "sess456"

    def test_system_user(self) -> None:
        """测试系统用户"""
        ctx = UserContext(user_id=SYSTEM_USER_ID)
        assert ctx.is_system

    def test_str_representation(self) -> None:
        """测试字符串表示"""
        ctx = UserContext(user_id="user123")
        assert "user123" in str(ctx)

        ctx_with_session = UserContext(user_id="user123", session_id="sess456")
        assert "sess456" in str(ctx_with_session)


class TestValidateUserId:
    """用户 ID 验证测试"""

    @pytest.mark.parametrize(
        "user_id",
        [
            "user123",
            "test_user",
            "user-name",
            "user.name",
            "ABC123",
            "a",
            "a" * 128,
        ],
    )
    def test_valid_user_ids(self, user_id: str) -> None:
        """测试有效的用户 ID"""
        assert _is_valid_user_id(user_id)

    @pytest.mark.parametrize(
        "user_id",
        [
            "",
            " ",
            "user name",
            "user@domain",
            "user/path",
            "user\\path",
            "<script>",
            "a" * 129,
        ],
    )
    def test_invalid_user_ids(self, user_id: str) -> None:
        """测试无效的用户 ID"""
        assert not _is_valid_user_id(user_id)


class TestCreateSystemContext:
    """系统上下文创建测试"""

    def test_basic(self) -> None:
        """测试基本创建"""
        ctx = create_system_context()
        assert ctx.user_id == SYSTEM_USER_ID
        assert ctx.is_system

    def test_with_request_id(self) -> None:
        """测试带请求 ID"""
        ctx = create_system_context(request_id="req123")
        assert ctx.request_id == "req123"


@pytest.mark.asyncio
class TestGetUserContext:
    """获取用户上下文测试"""

    async def test_valid_header(self) -> None:
        """测试有效的 header"""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.url.path = "/v1/servers"

        ctx = await get_user_context(
            request=request,
            x_witty_user="user123",
            x_witty_session="sess456",
            x_request_id="req789",
        )

        assert ctx.user_id == "user123"
        assert ctx.session_id == "sess456"
        assert ctx.request_id == "req789"

    async def test_missing_user_header(self) -> None:
        """测试缺少用户 header"""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.url.path = "/v1/servers"

        with pytest.raises(HTTPException) as exc_info:
            await get_user_context(
                request=request,
                x_witty_user=None,
            )

        assert exc_info.value.status_code == 401
        assert "MISSING_USER_IDENTITY" in str(exc_info.value.detail)

    async def test_invalid_user_id(self) -> None:
        """测试无效的用户 ID"""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.url.path = "/v1/servers"

        with pytest.raises(HTTPException) as exc_info:
            await get_user_context(
                request=request,
                x_witty_user="user@invalid",
            )

        assert exc_info.value.status_code == 400
        assert "INVALID_USER_ID" in str(exc_info.value.detail)


# =============================================================================
# Schemas 模块测试
# =============================================================================


class TestAPIResponse:
    """API 响应模型测试"""

    def test_success_response(self) -> None:
        """测试成功响应"""
        response = APIResponse(success=True, data={"key": "value"})
        assert response.success
        assert response.data == {"key": "value"}
        assert response.error is None

    def test_error_response(self) -> None:
        """测试错误响应"""
        response = APIResponse(
            success=False,
            error={"code": "TEST_ERROR", "message": "Test error"},
        )
        assert not response.success
        assert response.error is not None


class TestServerSummary:
    """Server 摘要模型测试"""

    def test_basic(self) -> None:
        """测试基本创建"""
        summary = ServerSummary(
            mcp_id="test_mcp",
            name="Test MCP",
            summary="Test summary",
            source="rpm",
            status="ready",
            user_enabled=True,
        )
        assert summary.mcp_id == "test_mcp"
        assert summary.status == "ready"
        assert summary.user_enabled


class TestToolSchema:
    """Tool 模型测试"""

    def test_basic(self) -> None:
        """测试基本创建"""
        tool = ToolSchema(
            name="test_tool",
            description="Test tool description",
            inputSchema={"type": "object", "properties": {}},
        )
        assert tool.name == "test_tool"
        assert tool.description == "Test tool description"


class TestToolCallRequest:
    """Tool 调用请求模型测试"""

    def test_with_arguments(self) -> None:
        """测试带参数"""
        request = ToolCallRequest(
            arguments={"key": "value"},
            timeout_ms=30000,
        )
        assert request.arguments == {"key": "value"}
        assert request.timeout_ms == 30000

    def test_defaults(self) -> None:
        """测试默认值"""
        request = ToolCallRequest(timeout_ms=None)
        assert request.arguments == {}
        assert request.timeout_ms is None


class TestToolCallResult:
    """Tool 调用结果模型测试"""

    def test_success(self) -> None:
        """测试成功结果"""
        result = ToolCallResult(
            content=[ContentItem(type="text", text="Hello")],
            isError=False,
        )
        assert not result.isError
        assert len(result.content) == 1
        assert result.content[0].text == "Hello"

    def test_error(self) -> None:
        """测试错误结果"""
        result = ToolCallResult(
            content=[ContentItem(type="text", text="Error message")],
            isError=True,
        )
        assert result.isError


class TestHealthStatus:
    """健康状态模型测试"""

    def test_basic(self) -> None:
        """测试基本创建"""
        status = HealthStatus(
            status="healthy",
            version="1.0.0",
            uptime_sec=3600,
            server_count=10,
            active_sessions=5,
        )
        assert status.status == "healthy"
        assert status.server_count == 10


class TestRuntimeStatus:
    """运行时状态模型测试"""

    def test_basic(self) -> None:
        """测试基本创建"""
        status = RuntimeStatus(
            mcp_id="test_mcp",
            user_id="user123",
            status="running",
            pid=12345,
        )
        assert status.mcp_id == "test_mcp"
        assert status.status == "running"
        assert status.pid == 12345


class TestCacheInfo:
    """缓存信息模型测试"""

    def test_basic(self) -> None:
        """测试基本创建"""
        now = datetime.now(UTC)
        info = CacheInfo(
            cached_at=now,
            expires_at=now,
            from_cache=True,
        )
        assert info.from_cache


# =============================================================================
# Server 模块测试
# =============================================================================


class TestIPCServerHelpers:
    """IPC Server 辅助函数测试"""

    def test_determine_server_status_ready(self) -> None:
        """测试就绪状态"""
        from witty_mcp_manager.ipc.routes.registry import _determine_server_status

        server = MagicMock()
        server.diagnostics = None

        status, reason = _determine_server_status(server)
        assert status == "ready"
        assert reason is None

    def test_determine_server_status_command_not_allowed(self) -> None:
        """测试命令不允许状态"""
        from witty_mcp_manager.ipc.routes.registry import _determine_server_status

        server = MagicMock()
        server.diagnostics = MagicMock()
        server.diagnostics.command_allowed = False
        server.diagnostics.errors = []
        # 设置 default_config 以提供命令信息
        server.default_config = MagicMock()
        server.default_config.stdio = MagicMock()
        server.default_config.stdio.command = "bash"

        status, reason = _determine_server_status(server)
        assert status == "unavailable"
        assert "bash" in reason  # type: ignore[operator]

    def test_determine_server_status_degraded(self) -> None:
        """测试降级状态"""
        from witty_mcp_manager.ipc.routes.registry import _determine_server_status

        server = MagicMock()
        server.diagnostics = MagicMock()
        server.diagnostics.command_allowed = True
        server.diagnostics.errors = []
        server.diagnostics.deps_missing = {"system": ["jq"]}

        status, reason = _determine_server_status(server)
        assert status == "degraded"
        assert "jq" in reason  # type: ignore[operator]

    def test_calculate_idle_time(self) -> None:
        """测试空闲时间计算"""
        from witty_mcp_manager.ipc.routes.runtime import _calculate_idle_time

        # None 返回 0
        assert _calculate_idle_time(None) == 0

        # 有值时计算差值
        past = datetime.now(UTC)
        idle = _calculate_idle_time(past)
        assert idle >= 0


# =============================================================================
# 集成测试（使用 TestClient）
# =============================================================================


class TestIPCServerIntegration:
    """IPC Server 集成测试"""

    @pytest.fixture
    def mock_dependencies(self) -> dict[str, Any]:
        """创建模拟依赖"""
        from witty_mcp_manager.config.config import ManagerConfig
        from witty_mcp_manager.diagnostics.checker import Checker
        from witty_mcp_manager.overlay.resolver import OverlayResolver
        from witty_mcp_manager.overlay.storage import OverlayStorage
        from witty_mcp_manager.registry.discovery import Discovery
        from witty_mcp_manager.registry.models import (
            Diagnostics,
            NormalizedConfig,
            ServerRecord,
            SourceType,
            StdioConfig,
            TransportType,
        )
        from witty_mcp_manager.runtime.manager import RuntimeManager

        # Mock config
        config = MagicMock(spec=ManagerConfig)
        config.scan_paths = []
        config.admin_sources = []

        # Mock discovery
        discovery = MagicMock(spec=Discovery)

        # 创建测试 ServerRecord
        test_server = ServerRecord(
            id="test_mcp",
            name="Test MCP Server",
            summary="Test summary",
            source=SourceType.RPM,
            install_root="/opt/mcp-servers/servers/test_mcp",
            upstream_key="test_mcp",
            transport=TransportType.STDIO,
            default_config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="python3", args=["server.py"]),
            ),
            diagnostics=Diagnostics(command_allowed=True, command_exists=True),
        )
        discovery.scan_all.return_value = [test_server]

        # Mock checker
        checker = MagicMock(spec=Checker)
        checker.validate.return_value = Diagnostics(command_allowed=True, command_exists=True)

        # Mock overlay storage
        overlay_storage = MagicMock(spec=OverlayStorage)
        overlay_storage.load_override.return_value = None
        overlay_storage.ensure_directories.return_value = None

        # Mock overlay resolver
        overlay_resolver = MagicMock(spec=OverlayResolver)

        # Mock runtime manager
        runtime_manager = MagicMock(spec=RuntimeManager)
        runtime_manager.list_sessions = AsyncMock(return_value=[])

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
    def test_client(self, mock_dependencies: dict[str, Any]) -> TestClient:
        """创建测试客户端"""
        from witty_mcp_manager.ipc.server import IPCServer, IPCServerConfig

        server_config = IPCServerConfig(
            config=mock_dependencies["config"],
            discovery=mock_dependencies["discovery"],
            checker=mock_dependencies["checker"],
            overlay_storage=mock_dependencies["overlay_storage"],
            overlay_resolver=mock_dependencies["overlay_resolver"],
            runtime_manager=mock_dependencies["runtime_manager"],
        )
        server = IPCServer(server_config)

        # 手动调用 startup 逻辑
        server._servers = {mock_dependencies["test_server"].id: mock_dependencies["test_server"]}  # noqa: SLF001
        server._started_at = datetime.now(UTC)  # noqa: SLF001

        return TestClient(server.app)

    def test_health_check(self, test_client: TestClient) -> None:
        """测试健康检查"""
        response = test_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["success"]
        assert data["data"]["status"] == "healthy"

    def test_list_servers_missing_auth(self, test_client: TestClient) -> None:
        """测试缺少认证的列表请求"""
        response = test_client.get("/v1/servers")
        assert response.status_code == 401

        data = response.json()
        assert not data["success"]
        assert data["error"]["code"] == "MISSING_USER_IDENTITY"

    def test_list_servers_with_auth(
        self,
        test_client: TestClient,
        mock_dependencies: dict[str, Any],
    ) -> None:
        """测试带认证的列表请求"""
        from witty_mcp_manager.overlay.resolver import EffectiveConfig
        from witty_mcp_manager.registry.models import (
            Concurrency,
            NormalizedConfig,
            StdioConfig,
            Timeouts,
            TransportType,
        )

        # Mock overlay resolver
        mock_dependencies["overlay_resolver"].resolve.return_value = EffectiveConfig(
            mcp_id="test_mcp",
            user_id="user123",
            disabled=False,
            config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="python3", args=["server.py"]),
            ),
            timeouts=Timeouts(),
            concurrency=Concurrency(),
        )

        response = test_client.get(
            "/v1/servers",
            headers={HEADER_USER_ID: "user123"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"]
        assert len(data["data"]) == 1
        assert data["data"][0]["mcp_id"] == "test_mcp"

    def test_get_server_not_found(self, test_client: TestClient) -> None:
        """测试获取不存在的 server"""
        response = test_client.get(
            "/v1/servers/nonexistent",
            headers={HEADER_USER_ID: "user123"},
        )
        assert response.status_code == 404

        data = response.json()
        assert not data["success"]
        assert data["error"]["code"] == "SERVER_NOT_FOUND"

    def test_enable_server(
        self,
        test_client: TestClient,
        mock_dependencies: dict[str, Any],
    ) -> None:
        """测试启用 server"""
        response = test_client.post(
            "/v1/me/servers/test_mcp/enable",
            headers={HEADER_USER_ID: "user123"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"]
        assert data["data"]["mcp_id"] == "test_mcp"
        assert data["data"]["enabled"]

        # 验证 save_override 被调用
        mock_dependencies["overlay_storage"].save_override.assert_called()

    def test_disable_server(
        self,
        test_client: TestClient,
        mock_dependencies: dict[str, Any],
    ) -> None:
        """测试禁用 server"""
        mock_dependencies["runtime_manager"].get_session = AsyncMock(return_value=None)

        response = test_client.post(
            "/v1/me/servers/test_mcp/disable",
            headers={HEADER_USER_ID: "user123"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"]
        assert data["data"]["mcp_id"] == "test_mcp"
        assert not data["data"]["enabled"]

    def test_enable_nonexistent_server(self, test_client: TestClient) -> None:
        """测试启用不存在的 server"""
        response = test_client.post(
            "/v1/me/servers/nonexistent/enable",
            headers={HEADER_USER_ID: "user123"},
        )
        assert response.status_code == 404

    def test_list_runtime_sessions(
        self,
        test_client: TestClient,
        mock_dependencies: dict[str, Any],
    ) -> None:
        """测试列出运行时会话"""
        response = test_client.get(
            "/v1/runtime/sessions",
            headers={HEADER_USER_ID: "user123"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"]
        assert data["data"] == []

    def test_get_session_not_found(
        self,
        test_client: TestClient,
        mock_dependencies: dict[str, Any],
    ) -> None:
        """测试获取不存在的会话"""
        mock_dependencies["runtime_manager"].get_session = AsyncMock(return_value=None)

        response = test_client.get(
            "/v1/runtime/sessions/test_mcp",
            headers={HEADER_USER_ID: "user123"},
        )
        assert response.status_code == 404

        data = response.json()
        assert data["error"]["code"] == "SESSION_NOT_FOUND"
