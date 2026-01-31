"""Witty MCP Manager 异常定义"""

from __future__ import annotations


class WittyMCPError(Exception):
    """Witty MCP Manager 基础异常"""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code or "WITTY_MCP_ERROR"


class ConfigurationError(WittyMCPError):
    """配置错误"""

    def __init__(self, message: str):
        super().__init__(message, "CONFIGURATION_ERROR")


class DiscoveryError(WittyMCPError):
    """服务发现错误"""

    def __init__(self, message: str, server_id: str | None = None):
        super().__init__(message, "DISCOVERY_ERROR")
        self.server_id = server_id


class NormalizationError(WittyMCPError):
    """配置标准化错误"""

    def __init__(self, message: str, server_id: str | None = None):
        super().__init__(message, "NORMALIZATION_ERROR")
        self.server_id = server_id


class DiagnosticsError(WittyMCPError):
    """诊断错误"""

    def __init__(self, message: str, server_id: str | None = None):
        super().__init__(message, "DIAGNOSTICS_ERROR")
        self.server_id = server_id


class AdapterError(WittyMCPError):
    """适配器错误"""

    def __init__(self, message: str, adapter_type: str | None = None):
        super().__init__(message, "ADAPTER_ERROR")
        self.adapter_type = adapter_type


class SessionError(WittyMCPError):
    """会话错误"""

    def __init__(self, message: str, user_id: str | None = None, mcp_id: str | None = None):
        super().__init__(message, "SESSION_ERROR")
        self.user_id = user_id
        self.mcp_id = mcp_id


class SecurityError(WittyMCPError):
    """安全错误"""

    def __init__(self, message: str, reason: str | None = None):
        super().__init__(message, "SECURITY_ERROR")
        self.reason = reason


class CommandNotAllowedError(SecurityError):
    """命令不在白名单中"""

    def __init__(self, command: str, allowlist: list[str] | None = None):
        super().__init__(
            f"Command '{command}' is not in allowlist",
            reason="COMMAND_NOT_ALLOWED",
        )
        self.command = command
        self.allowlist = allowlist or []


class ToolCallError(WittyMCPError):
    """Tool 调用错误"""

    def __init__(self, message: str, tool_name: str | None = None, mcp_id: str | None = None):
        super().__init__(message, "TOOL_CALL_ERROR")
        self.tool_name = tool_name
        self.mcp_id = mcp_id


class TimeoutError(WittyMCPError):
    """超时错误"""

    def __init__(self, message: str, timeout_seconds: int | None = None):
        super().__init__(message, "TIMEOUT_ERROR")
        self.timeout_seconds = timeout_seconds
