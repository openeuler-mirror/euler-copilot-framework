"""
API 数据模型

定义所有 IPC API 的请求/响应数据结构。
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Pydantic 运行时需要
from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# 通用响应模型
# =============================================================================


class APIResponse(BaseModel):
    """通用 API 响应"""

    success: bool = True
    data: Any = None
    error: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class ErrorDetail(BaseModel):
    """错误详情"""

    code: str
    message: str
    details: dict[str, Any] | None = None
    suggestion: str | None = None


# =============================================================================
# Registry API 模型
# =============================================================================


class ServerSummary(BaseModel):
    """MCP Server 摘要（用于列表展示）"""

    mcp_id: str = Field(..., description="MCP Server ID")
    name: str = Field(..., description="显示名称")
    summary: str = Field("", description="简要描述")
    source: str = Field(..., description="来源类型: rpm, admin, user")
    status: str = Field(..., description="状态: ready, degraded, unavailable")
    status_reason: str | None = Field(default=None, description="状态说明")
    user_enabled: bool = Field(default=False, description="当前用户是否已启用")


class ServerListResponse(BaseModel):
    """Server 列表响应"""

    success: bool = True
    data: list[ServerSummary] = Field(default_factory=list)


class ServerDetail(BaseModel):
    """MCP Server 详情"""

    mcp_id: str
    name: str
    summary: str = ""
    description: str = ""
    source: str
    transport: str
    install_root: str | None = None
    upstream_key: str | None = None

    # 状态
    status: str
    status_reason: str | None = None
    user_enabled: bool = False

    # 诊断信息
    diagnostics: DiagnosticsInfo | None = None

    # 配置
    effective_config: EffectiveConfigInfo | None = None


class DiagnosticsInfo(BaseModel):
    """诊断信息"""

    command_allowed: bool = True
    command: str | None = None
    allowed_commands: list[str] = Field(default_factory=list)
    deps_missing: DepsMissing | None = None
    files_valid: bool = True
    errors: list[str] = Field(default_factory=list)


class DepsMissing(BaseModel):
    """缺失依赖"""

    system: list[str] = Field(default_factory=list)
    python: list[str] = Field(default_factory=list)


class EffectiveConfigInfo(BaseModel):
    """生效配置信息"""

    transport: str
    tool_call_timeout_sec: int = 30
    idle_ttl_sec: int = 600
    max_concurrency: int = 5
    env: dict[str, str] = Field(default_factory=dict)


class ServerDetailResponse(BaseModel):
    """Server 详情响应"""

    success: bool = True
    data: ServerDetail | None = None


# =============================================================================
# Enable/Disable API 模型
# =============================================================================


class EnableDisableRequest(BaseModel):
    """启用/禁用请求（可选参数）"""



class EnableDisableResult(BaseModel):
    """启用/禁用结果"""

    mcp_id: str
    enabled: bool


class EnableDisableResponse(BaseModel):
    """启用/禁用响应"""

    success: bool = True
    data: EnableDisableResult | None = None


# =============================================================================
# Tools API 模型
# =============================================================================


class ToolSchema(BaseModel):
    """Tool 定义"""

    name: str = Field(..., description="Tool 名称")
    description: str = Field("", description="Tool 描述")
    inputSchema: dict[str, Any] = Field(default_factory=dict, description="输入参数 schema")  # noqa: N815


class CacheInfo(BaseModel):
    """缓存信息"""

    cached_at: datetime | None = None
    expires_at: datetime | None = None
    from_cache: bool = False


class ToolsListResult(BaseModel):
    """Tools 列表结果"""

    tools: list[ToolSchema] = Field(default_factory=list)
    cache_info: CacheInfo | None = None


class ToolsListResponse(BaseModel):
    """Tools 列表响应"""

    success: bool = True
    data: ToolsListResult | None = None


# =============================================================================
# Tool Call API 模型
# =============================================================================


class ToolCallRequest(BaseModel):
    """Tool 调用请求"""

    arguments: dict[str, Any] = Field(default_factory=dict, description="调用参数")
    timeout_ms: int | None = Field(None, description="超时时间（毫秒）")


class ContentItem(BaseModel):
    """内容项"""

    type: str = Field(..., description="内容类型: text, image, resource")
    text: str | None = None
    data: str | None = None
    mimeType: str | None = None  # noqa: N815


class ToolCallResult(BaseModel):
    """Tool 调用结果"""

    content: list[ContentItem] = Field(default_factory=list)
    isError: bool = Field(default=False, description="是否为错误结果")  # noqa: N815


class ToolCallMetadata(BaseModel):
    """Tool 调用元数据"""

    duration_ms: int = 0
    mcp_id: str = ""
    tool_name: str = ""
    from_cache: bool = False


class ToolCallResponse(BaseModel):
    """Tool 调用响应"""

    success: bool = True
    data: ToolCallResult | None = None
    metadata: ToolCallMetadata | None = None


# =============================================================================
# Runtime API 模型
# =============================================================================


class RuntimeStatus(BaseModel):
    """运行时状态"""

    mcp_id: str
    user_id: str
    status: str = Field(..., description="状态: starting, running, stopped, error")
    pid: int | None = None
    started_at: datetime | None = None
    last_used_at: datetime | None = None
    idle_time_sec: int = 0
    restart_count: int = 0
    error_count: int = 0
    last_error: str | None = None


class RuntimeStatusResponse(BaseModel):
    """运行时状态响应"""

    success: bool = True
    data: RuntimeStatus | None = None


class RuntimeListResponse(BaseModel):
    """运行时列表响应"""

    success: bool = True
    data: list[RuntimeStatus] = Field(default_factory=list)


# =============================================================================
# Health API 模型
# =============================================================================


class HealthStatus(BaseModel):
    """健康状态"""

    status: str = Field("healthy", description="健康状态: healthy, degraded, unhealthy")
    version: str = Field("", description="版本号")
    uptime_sec: int = Field(0, description="运行时间（秒）")
    server_count: int = Field(0, description="已注册 Server 数量")
    active_sessions: int = Field(0, description="活跃会话数量")


class HealthResponse(BaseModel):
    """健康检查响应"""

    success: bool = True
    data: HealthStatus | None = None
