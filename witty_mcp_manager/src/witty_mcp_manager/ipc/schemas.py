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

    success: bool = Field(default=True, description="请求是否成功")
    data: Any = Field(default=None, description="响应数据")
    error: dict[str, Any] | None = Field(default=None, description="错误信息")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")


class ErrorDetail(BaseModel):
    """错误详情"""

    code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    details: dict[str, Any] | None = Field(default=None, description="详细信息")
    suggestion: str | None = Field(default=None, description="解决建议")


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

    success: bool = Field(default=True, description="请求是否成功")
    data: list[ServerSummary] = Field(default_factory=list, description="Server 列表")


class ServerDetail(BaseModel):
    """MCP Server 详情"""

    mcp_id: str = Field(..., description="MCP Server ID")
    name: str = Field(..., description="显示名称")
    summary: str = Field(default="", description="简要描述")
    description: str = Field(default="", description="详细描述")
    source: str = Field(..., description="来源类型: rpm, admin, user")
    transport: str = Field(..., description="传输方式: stdio, sse")
    install_root: str | None = Field(default=None, description="安装根目录")
    upstream_key: str | None = Field(default=None, description="上游配置键")

    # 状态
    status: str = Field(..., description="状态: ready, degraded, unavailable")
    status_reason: str | None = Field(default=None, description="状态说明")
    user_enabled: bool = Field(default=False, description="当前用户是否已启用")

    # 诊断信息
    diagnostics: DiagnosticsInfo | None = Field(default=None, description="诊断信息")

    # 配置
    effective_config: EffectiveConfigInfo | None = Field(default=None, description="生效配置")


class DiagnosticsInfo(BaseModel):
    """诊断信息"""

    command_allowed: bool = Field(default=True, description="命令是否允许执行")
    command: str | None = Field(default=None, description="实际执行命令")
    allowed_commands: list[str] = Field(default_factory=list, description="允许的命令列表")
    deps_missing: DepsMissing | None = Field(default=None, description="缺失的依赖")
    files_valid: bool = Field(default=True, description="文件是否有效")
    errors: list[str] = Field(default_factory=list, description="错误列表")


class DepsMissing(BaseModel):
    """缺失依赖"""

    system: list[str] = Field(default_factory=list, description="缺失的系统依赖")
    python: list[str] = Field(default_factory=list, description="缺失的 Python 包")


class EffectiveConfigInfo(BaseModel):
    """生效配置信息"""

    transport: str = Field(..., description="传输方式: stdio, sse")
    tool_call_timeout_sec: int = Field(default=30, description="工具调用超时（秒）")
    idle_ttl_sec: int = Field(default=600, description="空闲存活时间（秒）")
    max_concurrency: int = Field(default=5, description="最大并发数")
    env: dict[str, str] = Field(default_factory=dict, description="环境变量")


class ServerDetailResponse(BaseModel):
    """Server 详情响应"""

    success: bool = Field(default=True, description="请求是否成功")
    data: ServerDetail | None = Field(default=None, description="Server 详情数据")


# =============================================================================
# Enable/Disable API 模型
# =============================================================================


class EnableDisableRequest(BaseModel):
    """启用/禁用请求（可选参数）"""



class EnableDisableResult(BaseModel):
    """启用/禁用结果"""

    mcp_id: str = Field(..., description="MCP Server ID")
    enabled: bool = Field(..., description="是否已启用")


class EnableDisableResponse(BaseModel):
    """启用/禁用响应"""

    success: bool = Field(default=True, description="请求是否成功")
    data: EnableDisableResult | None = Field(default=None, description="启用/禁用结果")


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

    cached_at: datetime | None = Field(default=None, description="缓存时间")
    expires_at: datetime | None = Field(default=None, description="过期时间")
    from_cache: bool = Field(default=False, description="是否来自缓存")


class ToolsListResult(BaseModel):
    """Tools 列表结果"""

    tools: list[ToolSchema] = Field(default_factory=list, description="工具列表")
    cache_info: CacheInfo | None = Field(default=None, description="缓存信息")


class ToolsListResponse(BaseModel):
    """Tools 列表响应"""

    success: bool = Field(default=True, description="请求是否成功")
    data: ToolsListResult | None = Field(default=None, description="Tools 列表数据")


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
    text: str | None = Field(default=None, description="文本内容")
    data: str | None = Field(default=None, description="数据内容（Base64编码）")
    mimeType: str | None = Field(default=None, description="MIME 类型")  # noqa: N815


class ToolCallResult(BaseModel):
    """Tool 调用结果"""

    content: list[ContentItem] = Field(default_factory=list)
    isError: bool = Field(default=False, description="是否为错误结果")  # noqa: N815


class ToolCallMetadata(BaseModel):
    """Tool 调用元数据"""

    duration_ms: int = Field(default=0, description="执行耗时（毫秒）")
    mcp_id: str = Field(default="", description="MCP Server ID")
    tool_name: str = Field(default="", description="工具名称")
    from_cache: bool = Field(default=False, description="是否来自缓存")


class ToolCallResponse(BaseModel):
    """Tool 调用响应"""

    success: bool = Field(default=True, description="请求是否成功")
    data: ToolCallResult | None = Field(default=None, description="调用结果数据")
    metadata: ToolCallMetadata | None = Field(default=None, description="调用元数据")


# =============================================================================
# Runtime API 模型
# =============================================================================


class RuntimeStatus(BaseModel):
    """运行时状态"""

    mcp_id: str = Field(..., description="MCP Server ID")
    user_id: str = Field(..., description="用户 ID")
    status: str = Field(..., description="状态: starting, running, stopped, error")
    pid: int | None = Field(default=None, description="进程 ID")
    started_at: datetime | None = Field(default=None, description="启动时间")
    last_used_at: datetime | None = Field(default=None, description="最后使用时间")
    idle_time_sec: int = Field(default=0, description="空闲时间（秒）")
    restart_count: int = Field(default=0, description="重启次数")
    error_count: int = Field(default=0, description="错误次数")
    last_error: str | None = Field(default=None, description="最后一次错误")


class RuntimeStatusResponse(BaseModel):
    """运行时状态响应"""

    success: bool = Field(default=True, description="请求是否成功")
    data: RuntimeStatus | None = Field(default=None, description="运行时状态数据")


class RuntimeListResponse(BaseModel):
    """运行时列表响应"""

    success: bool = Field(default=True, description="请求是否成功")
    data: list[RuntimeStatus] = Field(default_factory=list, description="运行时状态列表")


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

    success: bool = Field(default=True, description="请求是否成功")
    data: HealthStatus | None = Field(default=None, description="健康状态数据")
