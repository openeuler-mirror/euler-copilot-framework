from pydantic import BaseModel, Field  # noqa: D100
from pyparsing import Enum


class MCPManagerConfig(BaseModel):  # noqa: D101
    uds_path: str = Field(default="/run/witty/mcp-manager.sock")
    user_id: str = Field()
    timeout: int = Field(default=30)

class MCPStatus(str, Enum):  # noqa: D101, SLOT000
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABELE = "unavailable"

class MCPServerInfo(BaseModel):  # noqa: D101
    mcp_id: str = Field(...)
    name: str = Field(...)
    summary: str = Field(...)
    source: str = Field(...)
    status: MCPStatus = Field(...)
    status_reason:str | None = Field(None)
    user_enabled: bool = Field(...)
