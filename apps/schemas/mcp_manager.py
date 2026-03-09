"""MCP_Manager相关数据模型定义"""
from enum import StrEnum

from pydantic import BaseModel, Field  # noqa: D100


class MCPManagerConfig(BaseModel):  # noqa: D101
    uds_path: str = Field(default="/run/witty/mcp-manager.sock")
    user_id: str = Field()
    timeout: int = Field(default=30)


class MCPStatus(StrEnum):
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    READY = "ready"


class MCPServerInfo(BaseModel):
    mcp_id: str = Field(...)
    name: str = Field(...)
    summary: str = Field(...)
    source: str = Field(...)
    status: MCPStatus = Field(...)
    status_reason: str | None = Field(None)
    user_enabled: bool = Field(...)
