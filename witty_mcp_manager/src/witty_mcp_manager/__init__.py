"""Witty MCP Manager - Universal MCP Host/Loader for Witty AI Assistant.

统一管理多源 MCP：
- RPM 生态 MCP（/opt/mcp-servers/servers）
- 旧版 master mcp（oe-cli-mcp-server）
- 独立第三方 MCP Server
"""

__version__ = "1.0.0"
__author__ = "openEuler Community"

from witty_mcp_manager.registry.models import (
    NormalizedConfig,
    Override,
    RuntimeState,
    ServerRecord,
    SourceType,
    TransportType,
)

__all__ = [
    "__version__",
    "ServerRecord",
    "NormalizedConfig",
    "Override",
    "RuntimeState",
    "TransportType",
    "SourceType",
]
