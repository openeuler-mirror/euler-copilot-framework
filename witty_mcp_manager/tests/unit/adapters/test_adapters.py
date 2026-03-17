"""Adapter 单元测试

测试 STDIO 和 SSE 适配器的核心逻辑，不依赖真实的进程或网络连接。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from witty_mcp_manager.adapters.base import (
    AdapterType,
    Tool,
    ToolCallResult,
    ToolsCache,
)
from witty_mcp_manager.adapters.sse import SSEAdapter
from witty_mcp_manager.adapters.stdio import STDIOAdapter
from witty_mcp_manager.exceptions import AdapterError
from witty_mcp_manager.registry.models import (
    NormalizedConfig,
    ServerRecord,
    SourceType,
    SseConfig,
    StdioConfig,
    Timeouts,
    ToolPolicy,
    TransportType,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def stdio_server_record(tmp_path: Path) -> ServerRecord:
    """创建 STDIO 类型的 ServerRecord"""
    return ServerRecord(
        id="test_stdio_mcp",
        upstream_key="test-stdio",
        name="Test STDIO MCP",
        summary="Test STDIO adapter",
        source=SourceType.RPM,
        transport=TransportType.STDIO,
        install_root=str(tmp_path),
        default_config=NormalizedConfig(
            transport=TransportType.STDIO,
            stdio=StdioConfig(
                command="uv",
                args=["--directory", str(tmp_path), "run", "server.py"],
                env={"TEST_VAR": "value"},
            ),
            tool_policy=ToolPolicy(always_allow=["test_tool"]),
            timeouts=Timeouts(tool_call=60),
        ),
    )


@pytest.fixture
def sse_server_record(tmp_path: Path) -> ServerRecord:
    """创建 SSE 类型的 ServerRecord"""
    return ServerRecord(
        id="test_sse_mcp",
        upstream_key="test-sse",
        name="Test SSE MCP",
        summary="Test SSE adapter",
        source=SourceType.RPM,
        transport=TransportType.SSE,
        install_root=str(tmp_path),
        default_config=NormalizedConfig(
            transport=TransportType.SSE,
            sse=SseConfig(
                url="http://localhost:8080/sse",
                headers={"X-API-Key": "test"},
            ),
            tool_policy=ToolPolicy(),
            timeouts=Timeouts(tool_call=30),
        ),
    )


@pytest.fixture
def mock_effective_config():
    """创建 mock EffectiveConfig"""
    from witty_mcp_manager.overlay.resolver import EffectiveConfig

    config = MagicMock(spec=EffectiveConfig)
    config.disabled = False
    config.env = {"EXTRA_VAR": "extra_value"}
    config.headers = {}

    # mock config.config (NormalizedConfig)
    config.config = MagicMock()
    config.config.stdio = StdioConfig(
        command="uv",
        args=["run", "server.py"],
        env={"BASE_VAR": "base"},
    )
    config.config.sse = None
    config.config.timeouts = Timeouts(tool_call=60)
    config.config.tool_policy = ToolPolicy(always_allow=["allowed_tool"])

    return config


@pytest.fixture
def mock_sse_effective_config():
    """创建 SSE 类型的 mock EffectiveConfig"""
    from witty_mcp_manager.overlay.resolver import EffectiveConfig

    config = MagicMock(spec=EffectiveConfig)
    config.disabled = False
    config.env = {}
    config.headers = {"Authorization": "Bearer test"}

    config.config = MagicMock()
    config.config.stdio = None
    config.config.sse = SseConfig(
        url="http://localhost:8080/sse",
        headers={"X-API-Key": "default"},
    )
    config.config.timeouts = Timeouts(tool_call=30)
    config.config.tool_policy = ToolPolicy()

    return config


class TestToolModel:
    """Tool 模型测试"""

    def test_tool_creation(self):
        """测试 Tool 创建"""
        tool = Tool(
            name="test_tool",
            description="Test tool description",
            input_schema={"type": "object", "properties": {"arg1": {"type": "string"}}},
        )
        assert tool.name == "test_tool"
        assert tool.description == "Test tool description"
        assert "properties" in tool.input_schema

    def test_tool_without_schema(self):
        """测试无 schema 的 Tool"""
        tool = Tool(name="simple_tool")
        assert tool.name == "simple_tool"
        assert tool.description == ""
        assert tool.input_schema == {}

    def test_tool_to_dict(self):
        """测试 to_dict 方法"""
        tool = Tool(
            name="test_tool",
            description="desc",
            input_schema={"type": "object"},
        )
        result = tool.to_dict()
        assert result["name"] == "test_tool"
        assert result["description"] == "desc"
        assert result["inputSchema"] == {"type": "object"}


class TestToolCallResult:
    """ToolCallResult 模型测试"""

    def test_success_result(self):
        """测试成功结果"""
        result = ToolCallResult(
            success=True,
            content=[{"type": "text", "text": "Success"}],
            is_error=False,
        )
        assert result.success is True
        assert result.is_error is False
        assert len(result.content) == 1

    def test_error_result(self):
        """测试错误结果"""
        result = ToolCallResult(
            success=False,
            content=[{"type": "text", "text": "Error occurred"}],
            is_error=True,
            error="Something went wrong",
        )
        assert result.success is False
        assert result.is_error is True
        assert result.error == "Something went wrong"

    def test_to_dict(self):
        """测试 to_dict 方法"""
        result = ToolCallResult(
            success=True,
            content=[{"type": "text", "text": "OK"}],
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["content"] == [{"type": "text", "text": "OK"}]

    def test_error_result_factory(self):
        """测试 error_result 工厂方法"""
        result = ToolCallResult.error_result("Test error", duration_ms=100)
        assert result.success is False
        assert result.is_error is True
        assert result.error == "Test error"
        assert result.duration_ms == 100


class TestToolsCache:
    """ToolsCache 测试"""

    def test_cache_not_expired(self):
        """测试缓存未过期"""
        cache = ToolsCache(
            tools=[Tool(name="t1")],
            cached_at=datetime.now(UTC),
            ttl_seconds=600,
        )
        assert cache.is_expired is False

    def test_cache_expired(self):
        """测试缓存已过期"""
        from datetime import timedelta

        old_time = datetime.now(UTC) - timedelta(seconds=700)
        cache = ToolsCache(
            tools=[Tool(name="t1")],
            cached_at=old_time,
            ttl_seconds=600,
        )
        assert cache.is_expired is True


class TestSTDIOAdapter:
    """STDIO 适配器测试"""

    def test_adapter_type(self, stdio_server_record, mock_effective_config):
        """测试适配器类型"""
        adapter = STDIOAdapter(stdio_server_record, mock_effective_config)
        assert adapter.adapter_type == AdapterType.STDIO

    def test_mcp_id(self, stdio_server_record, mock_effective_config):
        """测试 mcp_id 属性"""
        adapter = STDIOAdapter(stdio_server_record, mock_effective_config)
        assert adapter.mcp_id == "test_stdio_mcp"

    def test_initial_not_connected(self, stdio_server_record, mock_effective_config):
        """测试初始状态未连接"""
        adapter = STDIOAdapter(stdio_server_record, mock_effective_config)
        assert adapter.is_connected is False

    def test_build_server_params(self, stdio_server_record, mock_effective_config):
        """测试 _build_server_params"""
        adapter = STDIOAdapter(stdio_server_record, mock_effective_config)
        params = adapter._build_server_params()  # noqa: SLF001

        assert params.command == "uv"
        assert "run" in params.args
        # env 应该合并
        assert params.env is not None
        assert "BASE_VAR" in params.env
        assert "EXTRA_VAR" in params.env

    def test_build_server_params_no_stdio_config(self, stdio_server_record):
        """测试缺失 STDIO 配置时的错误"""
        from witty_mcp_manager.overlay.resolver import EffectiveConfig

        config = MagicMock(spec=EffectiveConfig)
        config.config = MagicMock()
        config.config.stdio = None  # 没有 STDIO 配置
        config.env = {}

        adapter = STDIOAdapter(stdio_server_record, config)

        with pytest.raises(AdapterError) as exc_info:
            adapter._build_server_params()  # noqa: SLF001
        assert "STDIO config not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, stdio_server_record, mock_effective_config):
        """测试未连接时断开连接"""
        adapter = STDIOAdapter(stdio_server_record, mock_effective_config)
        # 应该不会抛出异常
        await adapter.disconnect()
        assert adapter.is_connected is False


class TestSSEAdapter:
    """SSE 适配器测试"""

    def test_adapter_type(self, sse_server_record, mock_sse_effective_config):
        """测试适配器类型"""
        adapter = SSEAdapter(sse_server_record, mock_sse_effective_config)
        assert adapter.adapter_type == AdapterType.SSE

    def test_mcp_id(self, sse_server_record, mock_sse_effective_config):
        """测试 mcp_id 属性"""
        adapter = SSEAdapter(sse_server_record, mock_sse_effective_config)
        assert adapter.mcp_id == "test_sse_mcp"

    def test_initial_not_connected(self, sse_server_record, mock_sse_effective_config):
        """测试初始状态未连接"""
        adapter = SSEAdapter(sse_server_record, mock_sse_effective_config)
        assert adapter.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, sse_server_record, mock_sse_effective_config):
        """测试未连接时断开连接"""
        adapter = SSEAdapter(sse_server_record, mock_sse_effective_config)
        await adapter.disconnect()
        assert adapter.is_connected is False

    def test_get_connection_urls_adds_ipv4_loopback_fallback(
        self,
        sse_server_record,
        mock_sse_effective_config,
    ):
        """localhost 应优先规范化为 127.0.0.1"""
        adapter = SSEAdapter(sse_server_record, mock_sse_effective_config)

        assert adapter._get_connection_urls() == [  # noqa: SLF001
            "http://127.0.0.1:8080/sse",
        ]

    def test_get_sse_url_normalizes_localhost_to_ipv4_loopback(
        self,
        sse_server_record,
        mock_sse_effective_config,
    ):
        """SSE URL 应直接规范化为 127.0.0.1，绕开 localhost 解析差异"""
        adapter = SSEAdapter(sse_server_record, mock_sse_effective_config)

        assert adapter._get_sse_url() == "http://127.0.0.1:8080/sse"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_connect_retries_with_ipv4_loopback_fallback(
        self,
        sse_server_record,
        mock_sse_effective_config,
    ):
        """localhost 连接失败后应回退到 127.0.0.1 重试"""
        adapter = SSEAdapter(sse_server_record, mock_sse_effective_config)
        session = MagicMock()
        session.mark_running = AsyncMock()
        session.stop = AsyncMock()

        good_client_context = AsyncMock()
        good_client_context.__aenter__.return_value = ("read", "write")
        good_client_context.__aexit__.return_value = None

        sse_client_calls: list[str] = []

        def fake_sse_client(*, url: str, headers: dict[str, str] | None = None):
            del headers
            sse_client_calls.append(url)
            if url == "http://127.0.0.1:8080/sse":
                failing_context = AsyncMock()
                failing_context.__aenter__.side_effect = OSError("connection refused")
                failing_context.__aexit__.return_value = None
                return failing_context
            return good_client_context

        client_session_context = AsyncMock()
        client_session_context.__aenter__.return_value = AsyncMock(initialize=AsyncMock())
        client_session_context.__aexit__.return_value = None

        with (
            patch("witty_mcp_manager.adapters.sse.sse_client", side_effect=fake_sse_client),
            patch("witty_mcp_manager.adapters.sse.ClientSession", return_value=client_session_context),
        ):
            with pytest.raises(AdapterError, match="Failed to connect"):
                await adapter.connect(session)

        assert sse_client_calls == ["http://127.0.0.1:8080/sse"]
        session.mark_running.assert_not_awaited()
        session.stop.assert_awaited_once()
        assert adapter.is_connected is False


class TestAdapterCreation:
    """适配器创建测试"""

    def test_create_stdio_adapter(self, stdio_server_record, mock_effective_config):
        """测试创建 STDIO 适配器"""
        from witty_mcp_manager.adapters.base import BaseAdapter

        adapter = STDIOAdapter(stdio_server_record, mock_effective_config)
        assert isinstance(adapter, STDIOAdapter)
        assert isinstance(adapter, BaseAdapter)

    def test_create_sse_adapter(self, sse_server_record, mock_sse_effective_config):
        """测试创建 SSE 适配器"""
        from witty_mcp_manager.adapters.base import BaseAdapter

        adapter = SSEAdapter(sse_server_record, mock_sse_effective_config)
        assert isinstance(adapter, SSEAdapter)
        assert isinstance(adapter, BaseAdapter)


class TestAdapterWithRealConfigs:
    """使用真实配置的适配器测试"""

    def test_stdio_adapter_with_git_mcp(
        self,
        mock_real_config,
        mock_real_mcp_servers_dir,
    ):
        """测试使用 git_mcp 真实配置创建适配器"""
        from witty_mcp_manager.overlay.resolver import OverlayResolver
        from witty_mcp_manager.overlay.storage import OverlayStorage
        from witty_mcp_manager.registry.discovery import Discovery

        discovery = Discovery(mock_real_config)
        servers = discovery.scan_all()
        git_mcp = next((s for s in servers if s.id == "git_mcp"), None)
        assert git_mcp is not None

        # 创建 resolver 和 effective config
        storage = OverlayStorage(mock_real_config.state_directory)
        resolver = OverlayResolver(storage)
        effective = resolver.resolve(git_mcp)

        # 创建适配器
        adapter = STDIOAdapter(git_mcp, effective)
        assert adapter.mcp_id == "git_mcp"
        assert adapter.adapter_type == AdapterType.STDIO

        # 验证 server params
        params = adapter._build_server_params()  # noqa: SLF001
        assert params.command == "uv"
        assert "--directory" in params.args

    def test_stdio_adapter_with_ccb_mcp(
        self,
        mock_real_config,
        mock_real_mcp_servers_dir,
    ):
        """测试使用 ccb_mcp 配置创建适配器（python3 命令）"""
        from witty_mcp_manager.overlay.resolver import OverlayResolver
        from witty_mcp_manager.overlay.storage import OverlayStorage
        from witty_mcp_manager.registry.discovery import Discovery

        discovery = Discovery(mock_real_config)
        servers = discovery.scan_all()
        ccb_mcp = next((s for s in servers if s.id == "ccb_mcp"), None)
        assert ccb_mcp is not None

        storage = OverlayStorage(mock_real_config.state_directory)
        resolver = OverlayResolver(storage)
        effective = resolver.resolve(ccb_mcp)

        adapter = STDIOAdapter(ccb_mcp, effective)
        params = adapter._build_server_params()  # noqa: SLF001

        assert params.command == "python3"

    def test_adapter_env_merging(
        self,
        mock_real_config,
        mock_real_mcp_servers_dir,
    ):
        """测试环境变量合并"""
        from witty_mcp_manager.overlay.resolver import OverlayResolver
        from witty_mcp_manager.overlay.storage import OverlayStorage
        from witty_mcp_manager.registry.discovery import Discovery
        from witty_mcp_manager.registry.models import Override

        discovery = Discovery(mock_real_config)
        servers = discovery.scan_all()
        cvekit = next((s for s in servers if s.id == "cvekit_mcp"), None)
        assert cvekit is not None

        storage = OverlayStorage(mock_real_config.state_directory)

        # 添加 user override 覆盖 env
        override = Override(
            scope="user/test_user",
            disabled=False,
            env={"GITEE_TOKEN": "user_token"},
        )
        storage.save_override("cvekit_mcp", override, user_id="test_user")

        resolver = OverlayResolver(storage)
        effective = resolver.resolve(cvekit, user_id="test_user")

        adapter = STDIOAdapter(cvekit, effective)
        params = adapter._build_server_params()  # noqa: SLF001

        # env 应该包含原始的 LANG 和 overlay 的 GITEE_TOKEN
        assert params.env is not None
        assert params.env.get("LANG") == "en_US.UTF-8"
        assert params.env.get("GITEE_TOKEN") == "user_token"
