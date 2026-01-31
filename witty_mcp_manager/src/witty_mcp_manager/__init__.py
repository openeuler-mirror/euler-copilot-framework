"""
Witty MCP Manager - Universal MCP Host/Loader for Witty AI Assistant.

统一管理多源 MCP：
- RPM 生态 MCP（/opt/mcp-servers/servers）
- 旧版 master mcp（oe-cli-mcp-server）
- 独立第三方 MCP Server
"""

__version__ = "1.0.0"
__author__ = "openEuler Community"

from witty_mcp_manager.overlay import OverlayResolver, OverlayStorage
from witty_mcp_manager.registry.models import (
    NormalizedConfig,
    Override,
    RuntimeState,
    ServerRecord,
    SourceType,
    TransportType,
)
from witty_mcp_manager.runtime import RuntimeManager, SessionRecycler
from witty_mcp_manager.security import CommandAllowlist, LogRedactor, SecretsManager

__all__ = [
    "CommandAllowlist",
    "LogRedactor",
    "NormalizedConfig",
    "OverlayResolver",
    "OverlayStorage",
    "Override",
    "RuntimeManager",
    "RuntimeState",
    "SecretsManager",
    "ServerRecord",
    "SessionRecycler",
    "SourceType",
    "TransportType",
    "__version__",
]
