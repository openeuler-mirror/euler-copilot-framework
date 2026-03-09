"""registry/models 模块单元测试

测试所有 Pydantic 模型的验证逻辑、computed_field 和边界条件。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from witty_mcp_manager.registry.models import (
    Concurrency,
    Diagnostics,
    NormalizedConfig,
    Override,
    RuntimeState,
    RuntimeStatus,
    ServerRecord,
    SourceType,
    SseConfig,
    StdioConfig,
    Timeouts,
    ToolPolicy,
    TransportType,
)


class TestStdioConfig:
    """StdioConfig 模型测试"""

    def test_valid_config(self) -> None:
        """测试有效配置"""
        config = StdioConfig(command="uv", args=["run", "server.py"])
        assert config.command == "uv"
        assert config.args == ["run", "server.py"]
        assert config.env == {}
        assert config.cwd is None

    def test_command_strip_whitespace(self) -> None:
        """测试命令去除空白"""
        config = StdioConfig(command="  uv  ")
        assert config.command == "uv"

    def test_empty_command_raises(self) -> None:
        """测试空命令抛出异常"""
        with pytest.raises(ValidationError, match="string_too_short"):
            StdioConfig(command="")

    def test_whitespace_command_raises(self) -> None:
        """测试纯空白命令抛出异常"""
        with pytest.raises(ValidationError, match="command cannot be empty or whitespace"):
            StdioConfig(command="   ")

    def test_with_env_and_cwd(self) -> None:
        """测试带 env 和 cwd"""
        config = StdioConfig(
            command="python3",
            args=["-m", "server"],
            env={"LANG": "en_US.UTF-8"},
            cwd="/opt/mcp",
        )
        assert config.env == {"LANG": "en_US.UTF-8"}
        assert config.cwd == "/opt/mcp"

    def test_extra_fields_forbidden(self) -> None:
        """测试禁止额外字段"""
        with pytest.raises(ValidationError):
            StdioConfig(command="uv", unknown_field="value")  # type: ignore[call-arg]


class TestSseConfig:
    """SseConfig 模型测试"""

    def test_valid_config(self) -> None:
        """测试有效配置"""
        config = SseConfig(url="http://localhost:8080/sse")
        assert config.url == "http://localhost:8080/sse"
        assert config.headers == {}
        assert config.timeout == 60

    def test_https_url(self) -> None:
        """测试 HTTPS URL"""
        config = SseConfig(url="https://api.example.com/mcp")
        assert config.url == "https://api.example.com/mcp"

    def test_invalid_url_scheme(self) -> None:
        """测试无效 URL 格式"""
        with pytest.raises(ValidationError, match="URL must start with"):
            SseConfig(url="ftp://invalid.com/sse")

    def test_with_headers(self) -> None:
        """测试带请求头"""
        config = SseConfig(
            url="http://localhost:8080/sse",
            headers={"Authorization": "Bearer token123"},
        )
        assert "Authorization" in config.headers

    def test_custom_timeout(self) -> None:
        """测试自定义超时"""
        config = SseConfig(url="http://localhost:8080/sse", timeout=120)
        assert config.timeout == 120

    def test_timeout_out_of_range(self) -> None:
        """测试超时值超范围"""
        with pytest.raises(ValidationError):
            SseConfig(url="http://localhost:8080/sse", timeout=0)

        with pytest.raises(ValidationError):
            SseConfig(url="http://localhost:8080/sse", timeout=8000)


class TestTimeouts:
    """Timeouts 模型测试"""

    def test_defaults(self) -> None:
        """测试默认值"""
        t = Timeouts()
        assert t.tool_call == 30
        assert t.connect == 10
        assert t.idle_ttl == 600

    def test_custom_values(self) -> None:
        """测试自定义值"""
        t = Timeouts(tool_call=60, connect=5, idle_ttl=1200)
        assert t.tool_call == 60
        assert t.connect == 5
        assert t.idle_ttl == 1200

    def test_invalid_tool_call_timeout(self) -> None:
        """测试无效的 tool_call 超时"""
        with pytest.raises(ValidationError):
            Timeouts(tool_call=0)

    def test_idle_ttl_zero_allowed(self) -> None:
        """测试 idle_ttl 允许为 0"""
        t = Timeouts(idle_ttl=0)
        assert t.idle_ttl == 0


class TestConcurrency:
    """Concurrency 模型测试"""

    def test_defaults(self) -> None:
        """测试默认值"""
        c = Concurrency()
        assert c.max_per_user == 5
        assert c.max_global == 100

    def test_valid_custom(self) -> None:
        """测试有效自定义值"""
        c = Concurrency(max_per_user=10, max_global=50)
        assert c.max_per_user == 10
        assert c.max_global == 50

    def test_per_user_exceeds_global_raises(self) -> None:
        """测试 max_per_user > max_global 抛出异常"""
        with pytest.raises(ValidationError, match="cannot exceed"):
            Concurrency(max_per_user=200, max_global=100)

    def test_zero_not_allowed(self) -> None:
        """测试 0 不允许"""
        with pytest.raises(ValidationError):
            Concurrency(max_per_user=0)


class TestToolPolicy:
    """ToolPolicy 模型测试"""

    def test_defaults(self) -> None:
        """测试默认值"""
        tp = ToolPolicy()
        assert tp.cache_ttl == 600
        assert tp.auto_discover is True
        assert tp.always_allow == []

    def test_with_always_allow(self) -> None:
        """测试设置 always_allow"""
        tp = ToolPolicy(always_allow=["read_file", "list_directory"])
        assert len(tp.always_allow) == 2
        assert "read_file" in tp.always_allow


class TestNormalizedConfig:
    """NormalizedConfig 模型测试"""

    def test_valid_stdio_config(self) -> None:
        """测试有效的 STDIO 配置"""
        config = NormalizedConfig(
            transport=TransportType.STDIO,
            stdio=StdioConfig(command="uv", args=["run"]),
        )
        assert config.transport == TransportType.STDIO
        assert config.stdio is not None
        assert config.sse is None

    def test_valid_sse_config(self) -> None:
        """测试有效的 SSE 配置"""
        config = NormalizedConfig(
            transport=TransportType.SSE,
            sse=SseConfig(url="http://localhost:8080/sse"),
        )
        assert config.transport == TransportType.SSE
        assert config.sse is not None
        assert config.stdio is None

    def test_stdio_without_config_raises(self) -> None:
        """测试 STDIO 传输缺少 stdio 配置"""
        with pytest.raises(ValidationError, match="STDIO transport requires stdio config"):
            NormalizedConfig(transport=TransportType.STDIO)

    def test_sse_without_config_raises(self) -> None:
        """测试 SSE 传输缺少 sse 配置"""
        with pytest.raises(ValidationError, match="SSE transport requires sse config"):
            NormalizedConfig(transport=TransportType.SSE)

    def test_stdio_with_sse_config_raises(self) -> None:
        """测试 STDIO 传输有 sse 配置抛出异常"""
        with pytest.raises(ValidationError, match="should not have sse config"):
            NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="uv"),
                sse=SseConfig(url="http://localhost:8080/sse"),
            )

    def test_sse_with_stdio_config_raises(self) -> None:
        """测试 SSE 传输有 stdio 配置抛出异常"""
        with pytest.raises(ValidationError, match="should not have stdio config"):
            NormalizedConfig(
                transport=TransportType.SSE,
                sse=SseConfig(url="http://localhost:8080/sse"),
                stdio=StdioConfig(command="uv"),
            )

    def test_extras_preserved(self) -> None:
        """测试扩展字段保留"""
        config = NormalizedConfig(
            transport=TransportType.STDIO,
            stdio=StdioConfig(command="uv"),
            extras={"description": "test"},
        )
        assert config.extras == {"description": "test"}


class TestDiagnostics:
    """Diagnostics 模型测试"""

    def test_default_healthy(self) -> None:
        """测试默认健康状态"""
        diag = Diagnostics()
        assert diag.command_allowed is True
        assert diag.command_exists is True
        assert diag.config_valid is True
        assert diag.errors == []
        assert diag.warnings == []
        assert diag.has_error is False
        assert diag.has_warning is False
        assert diag.is_ready is True
        assert diag.status == "ready"

    def test_with_errors(self) -> None:
        """测试错误状态"""
        diag = Diagnostics(errors=["Missing config file"])
        assert diag.has_error is True
        assert diag.is_ready is False
        assert diag.status == "unavailable"

    def test_with_warnings(self) -> None:
        """测试警告状态"""
        diag = Diagnostics(warnings=["Optional dependency missing"])
        assert diag.has_warning is True
        assert diag.is_ready is True
        assert diag.status == "degraded"

    def test_command_not_allowed(self) -> None:
        """测试命令不允许"""
        diag = Diagnostics(command_allowed=False)
        assert diag.is_ready is False
        assert diag.status == "unavailable"

    def test_config_invalid(self) -> None:
        """测试配置无效"""
        diag = Diagnostics(config_valid=False)
        assert diag.is_ready is False

    def test_deps_missing_default(self) -> None:
        """测试默认依赖缺失结构"""
        diag = Diagnostics()
        assert "system" in diag.deps_missing
        assert "python" in diag.deps_missing
        assert "packages" in diag.deps_missing


class TestServerRecord:
    """ServerRecord 模型测试"""

    def test_valid_record(self, tmp_path) -> None:
        """测试有效记录"""
        record = ServerRecord(
            id="git_mcp",
            name="Git MCP",
            source=SourceType.RPM,
            install_root=str(tmp_path),
            upstream_key="git_mcp",
            transport=TransportType.STDIO,
            default_config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="uv"),
            ),
        )
        assert record.id == "git_mcp"
        assert record.source == SourceType.RPM
        assert record.transport == TransportType.STDIO

    def test_transport_mismatch_raises(self, tmp_path) -> None:
        """测试 transport 与 config 不匹配"""
        with pytest.raises(ValidationError, match="must match"):
            ServerRecord(
                id="test",
                name="Test",
                source=SourceType.RPM,
                install_root=str(tmp_path),
                upstream_key="test",
                transport=TransportType.STDIO,
                default_config=NormalizedConfig(
                    transport=TransportType.SSE,
                    sse=SseConfig(url="http://localhost:8080/sse"),
                ),
            )

    def test_default_values(self, tmp_path) -> None:
        """测试默认值"""
        record = ServerRecord(
            id="test",
            name="Test",
            source=SourceType.RPM,
            install_root=str(tmp_path),
            upstream_key="test",
            transport=TransportType.STDIO,
            default_config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="uv"),
            ),
        )
        assert record.summary == ""
        assert record.default_disabled is False
        assert record.rpm_metadata == {}

    def test_admin_source_type(self, tmp_path) -> None:
        """测试 admin 来源类型"""
        record = ServerRecord(
            id="rag_mcp",
            name="RAG MCP",
            source=SourceType.ADMIN,
            install_root=str(tmp_path),
            upstream_key="rag_mcp",
            transport=TransportType.SSE,
            default_config=NormalizedConfig(
                transport=TransportType.SSE,
                sse=SseConfig(url="http://127.0.0.1:12311/sse"),
            ),
        )
        assert record.source == SourceType.ADMIN


class TestOverride:
    """Override 模型测试"""

    def test_global_scope(self) -> None:
        """测试全局作用域"""
        override = Override(scope="global", disabled=True)
        assert override.scope == "global"
        assert override.disabled is True

    def test_user_scope(self) -> None:
        """测试用户作用域"""
        override = Override(scope="user/alice", disabled=False)
        assert override.scope == "user/alice"

    def test_user_scope_with_dots_and_dashes(self) -> None:
        """测试用户名包含点和横线"""
        override = Override(scope="user/alice-bob.test")
        assert override.scope == "user/alice-bob.test"

    def test_invalid_scope_raises(self) -> None:
        """测试无效作用域"""
        with pytest.raises(ValidationError):
            Override(scope="invalid_scope")

        with pytest.raises(ValidationError):
            Override(scope="user/")

    def test_default_values(self) -> None:
        """测试默认值"""
        override = Override(scope="global")
        assert override.disabled is None
        assert override.env == {}
        assert override.headers == {}
        assert override.timeouts is None
        assert override.concurrency is None
        assert override.arg_patches == []

    def test_with_arg_patches(self) -> None:
        """测试参数补丁"""
        override = Override(
            scope="user/alice",
            arg_patches=[
                {"op": "add", "value": "--verbose"},
                {"op": "remove", "pattern": "--debug"},
            ],
        )
        assert len(override.arg_patches) == 2


class TestRuntimeState:
    """RuntimeState 模型测试"""

    def test_basic_creation(self) -> None:
        """测试基本创建"""
        state = RuntimeState(user_id="user123", mcp_id="git_mcp")
        assert state.user_id == "user123"
        assert state.mcp_id == "git_mcp"
        assert state.status == RuntimeStatus.STOPPED
        assert state.pid is None
        assert state.restart_count == 0

    def test_session_key(self) -> None:
        """测试 session_key 计算属性"""
        state = RuntimeState(user_id="user123", mcp_id="git_mcp")
        assert state.session_key == "user123:git_mcp"

    def test_running_status(self) -> None:
        """测试运行中状态"""
        state = RuntimeState(
            user_id="user123",
            mcp_id="git_mcp",
            status=RuntimeStatus.RUNNING,
            pid=12345,
        )
        assert state.is_running is True

    def test_stopped_status(self) -> None:
        """测试停止状态"""
        state = RuntimeState(user_id="user123", mcp_id="git_mcp")
        assert state.is_running is False


class TestEnums:
    """枚举类型测试"""

    def test_transport_type_values(self) -> None:
        """测试传输类型值"""
        assert TransportType.STDIO.value == "stdio"
        assert TransportType.SSE.value == "sse"
        assert TransportType.STREAMABLE_HTTP.value == "streamable_http"

    def test_source_type_values(self) -> None:
        """测试来源类型值"""
        assert SourceType.RPM.value == "rpm"
        assert SourceType.ADMIN.value == "admin"
        assert SourceType.USER.value == "user"

    def test_runtime_status_values(self) -> None:
        """测试运行时状态值"""
        assert RuntimeStatus.STARTING.value == "starting"
        assert RuntimeStatus.RUNNING.value == "running"
        assert RuntimeStatus.STOPPED.value == "stopped"
        assert RuntimeStatus.ERROR.value == "error"
