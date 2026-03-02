"""exceptions 模块单元测试

测试所有异常类的创建、属性和继承关系。
"""

from __future__ import annotations

import pytest

from witty_mcp_manager.exceptions import (
    AdapterError,
    CommandNotAllowedError,
    ConfigError,
    ConfigurationError,
    DiagnosticsError,
    DiscoveryError,
    MCPTimeoutError,
    NormalizationError,
    SecurityError,
    SessionError,
    ToolCallError,
    WittyMCPError,
    WittyRuntimeError,
)


class TestWittyMCPError:
    """基础异常测试"""

    def test_basic_creation(self) -> None:
        """测试基本创建"""
        err = WittyMCPError("Something went wrong")
        assert str(err) == "Something went wrong"
        assert err.message == "Something went wrong"
        assert err.code == "WITTY_MCP_ERROR"

    def test_custom_code(self) -> None:
        """测试自定义错误码"""
        err = WittyMCPError("Error", code="CUSTOM_CODE")
        assert err.code == "CUSTOM_CODE"

    def test_is_exception(self) -> None:
        """测试继承自 Exception"""
        err = WittyMCPError("test")
        assert isinstance(err, Exception)

    def test_raise_and_catch(self) -> None:
        """测试可以正常抛出和捕获"""
        msg = "test error"
        with pytest.raises(WittyMCPError, match="test error"):
            raise WittyMCPError(msg)


class TestConfigurationError:
    """配置错误测试"""

    def test_creation(self) -> None:
        """测试创建"""
        err = ConfigurationError("Invalid config")
        assert err.message == "Invalid config"
        assert err.code == "CONFIGURATION_ERROR"
        assert isinstance(err, WittyMCPError)


class TestDiscoveryError:
    """服务发现错误测试"""

    def test_creation(self) -> None:
        """测试创建"""
        err = DiscoveryError("Server not found")
        assert err.code == "DISCOVERY_ERROR"
        assert err.server_id is None

    def test_with_server_id(self) -> None:
        """测试带 server_id"""
        err = DiscoveryError("Failed to parse", server_id="git_mcp")
        assert err.server_id == "git_mcp"


class TestNormalizationError:
    """标准化错误测试"""

    def test_creation(self) -> None:
        """测试创建"""
        err = NormalizationError("Invalid format")
        assert err.code == "NORMALIZATION_ERROR"
        assert err.server_id is None

    def test_with_server_id(self) -> None:
        """测试带 server_id"""
        err = NormalizationError("Bad config", server_id="test_mcp")
        assert err.server_id == "test_mcp"


class TestDiagnosticsError:
    """诊断错误测试"""

    def test_creation(self) -> None:
        """测试创建"""
        err = DiagnosticsError("Check failed")
        assert err.code == "DIAGNOSTICS_ERROR"
        assert err.server_id is None

    def test_with_server_id(self) -> None:
        """测试带 server_id"""
        err = DiagnosticsError("Preflight fail", server_id="ccb_mcp")
        assert err.server_id == "ccb_mcp"


class TestAdapterError:
    """适配器错误测试"""

    def test_creation(self) -> None:
        """测试创建"""
        err = AdapterError("Connection failed")
        assert err.code == "ADAPTER_ERROR"
        assert err.adapter_type is None

    def test_with_adapter_type(self) -> None:
        """测试带适配器类型"""
        err = AdapterError("Timeout", adapter_type="stdio")
        assert err.adapter_type == "stdio"


class TestSessionError:
    """会话错误测试"""

    def test_creation(self) -> None:
        """测试创建"""
        err = SessionError("Session failed")
        assert err.code == "SESSION_ERROR"
        assert err.user_id is None
        assert err.mcp_id is None

    def test_with_context(self) -> None:
        """测试带上下文"""
        err = SessionError("Max retries", user_id="alice", mcp_id="git_mcp")
        assert err.user_id == "alice"
        assert err.mcp_id == "git_mcp"


class TestSecurityError:
    """安全错误测试"""

    def test_creation(self) -> None:
        """测试创建"""
        err = SecurityError("Access denied")
        assert err.code == "SECURITY_ERROR"
        assert err.reason is None

    def test_with_reason(self) -> None:
        """测试带原因"""
        err = SecurityError("Forbidden", reason="IP_BLOCKED")
        assert err.reason == "IP_BLOCKED"


class TestCommandNotAllowedError:
    """命令不允许错误测试"""

    def test_creation(self) -> None:
        """测试创建"""
        err = CommandNotAllowedError("bash")
        assert "bash" in str(err)
        assert err.command == "bash"
        assert err.allowlist == []
        assert err.reason == "COMMAND_NOT_ALLOWED"

    def test_with_allowlist(self) -> None:
        """测试带白名单"""
        err = CommandNotAllowedError("rm", allowlist=["uv", "python3"])
        assert err.command == "rm"
        assert err.allowlist == ["uv", "python3"]

    def test_inherits_security_error(self) -> None:
        """测试继承自 SecurityError"""
        err = CommandNotAllowedError("curl")
        assert isinstance(err, SecurityError)
        assert isinstance(err, WittyMCPError)


class TestConfigError:
    """通用配置错误测试"""

    def test_creation(self) -> None:
        """测试创建"""
        err = ConfigError("Config parse failed")
        assert err.code == "CONFIG_ERROR"
        assert isinstance(err, WittyMCPError)


class TestWittyRuntimeError:
    """运行时错误测试"""

    def test_creation(self) -> None:
        """测试创建"""
        err = WittyRuntimeError("Process crashed")
        assert err.code == "RUNTIME_ERROR"
        assert isinstance(err, WittyMCPError)


class TestToolCallError:
    """Tool 调用错误测试"""

    def test_creation(self) -> None:
        """测试创建"""
        err = ToolCallError("Tool execution failed")
        assert err.code == "TOOL_CALL_ERROR"
        assert err.tool_name is None
        assert err.mcp_id is None

    def test_with_context(self) -> None:
        """测试带上下文"""
        err = ToolCallError("Timeout", tool_name="git_status", mcp_id="git_mcp")
        assert err.tool_name == "git_status"
        assert err.mcp_id == "git_mcp"


class TestMCPTimeoutError:
    """超时错误测试"""

    def test_creation(self) -> None:
        """测试创建"""
        err = MCPTimeoutError("Operation timed out")
        assert err.code == "TIMEOUT_ERROR"
        assert err.timeout_seconds is None

    def test_with_timeout(self) -> None:
        """测试带超时秒数"""
        err = MCPTimeoutError("Timed out after 30s", timeout_seconds=30)
        assert err.timeout_seconds == 30


class TestExceptionHierarchy:
    """异常继承层级测试"""

    @pytest.mark.parametrize(
        "exc_class",
        [
            ConfigurationError,
            DiscoveryError,
            NormalizationError,
            DiagnosticsError,
            AdapterError,
            SessionError,
            SecurityError,
            ConfigError,
            WittyRuntimeError,
            ToolCallError,
            MCPTimeoutError,
        ],
    )
    def test_all_inherit_from_base(self, exc_class: type) -> None:
        """测试所有异常继承自 WittyMCPError"""
        assert issubclass(exc_class, WittyMCPError)
        assert issubclass(exc_class, Exception)

    def test_command_not_allowed_chain(self) -> None:
        """测试 CommandNotAllowedError 继承链"""
        assert issubclass(CommandNotAllowedError, SecurityError)
        assert issubclass(CommandNotAllowedError, WittyMCPError)
        assert issubclass(CommandNotAllowedError, Exception)
