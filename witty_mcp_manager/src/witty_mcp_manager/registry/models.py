"""Witty MCP Manager 数据模型定义"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TransportType(str, Enum):
    """MCP Transport 类型"""

    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable_http"


class SourceType(str, Enum):
    """MCP 来源类型"""

    RPM = "rpm"  # RPM 生态 MCP
    ADMIN = "admin"  # 管理员配置（如旧版 master mcp）
    USER = "user"  # 用户自定义


class StdioConfig(BaseModel):
    """STDIO 传输配置"""

    command: str = Field(..., description="启动命令")
    args: list[str] = Field(default_factory=list, description="命令参数")
    env: dict[str, str] = Field(default_factory=dict, description="环境变量")
    cwd: str | None = Field(default=None, description="工作目录")


class SseConfig(BaseModel):
    """SSE 传输配置"""

    url: str = Field(..., description="SSE 服务 URL")
    headers: dict[str, str] = Field(default_factory=dict, description="请求头")
    timeout: int = Field(default=60, description="连接超时（秒）")


class Timeouts(BaseModel):
    """超时配置"""

    tool_call: int = Field(default=30, description="Tool 调用超时（秒）")
    connect: int = Field(default=10, description="连接超时（秒）")
    idle_ttl: int = Field(default=600, description="空闲 TTL（秒）")


class Concurrency(BaseModel):
    """并发配置"""

    max_per_user: int = Field(default=5, description="每用户最大并发")
    max_global: int = Field(default=100, description="全局最大并发")


class ToolPolicy(BaseModel):
    """Tool 策略配置"""

    cache_ttl: int = Field(default=600, description="Tools 缓存 TTL（秒）")
    auto_discover: bool = Field(default=True, description="自动发现 Tools")
    always_allow: list[str] = Field(default_factory=list, description="始终允许的 Tools")


class NormalizedConfig(BaseModel):
    """标准化配置

    将不同格式的 MCP 配置统一为标准格式
    """

    transport: TransportType = Field(..., description="传输类型")
    stdio: StdioConfig | None = Field(default=None, description="STDIO 配置")
    sse: SseConfig | None = Field(default=None, description="SSE 配置")
    tool_policy: ToolPolicy = Field(default_factory=ToolPolicy, description="Tool 策略")
    timeouts: Timeouts = Field(default_factory=Timeouts, description="超时配置")
    extras: dict[str, Any] = Field(default_factory=dict, description="扩展字段（保留未知配置）")


class Diagnostics(BaseModel):
    """诊断信息

    记录 MCP Server 的配置检查结果
    """

    command_allowed: bool = Field(default=True, description="命令是否在白名单中")
    command_exists: bool = Field(default=True, description="命令是否存在")
    config_valid: bool = Field(default=True, description="配置是否有效")
    deps_missing: dict[str, list[str]] = Field(
        default_factory=lambda: {"system": [], "python": [], "packages": []},
        description="缺失的依赖",
    )
    errors: list[str] = Field(default_factory=list, description="错误列表")
    warnings: list[str] = Field(default_factory=list, description="警告列表")
    suggestions: list[str] = Field(default_factory=list, description="修复建议")

    @property
    def has_error(self) -> bool:
        """是否有错误"""
        return len(self.errors) > 0

    @property
    def has_warning(self) -> bool:
        """是否有警告"""
        return len(self.warnings) > 0

    @property
    def is_ready(self) -> bool:
        """是否可用"""
        return self.command_allowed and self.config_valid and not self.has_error

    @property
    def status(self) -> str:
        """状态字符串"""
        if not self.is_ready:
            return "unavailable"
        if self.has_warning:
            return "degraded"
        return "ready"


class ServerRecord(BaseModel):
    """MCP Server 记录

    统一表示不同来源的 MCP Server
    """

    id: str = Field(..., description="唯一标识（通常为目录名）")
    name: str = Field(..., description="显示名称")
    summary: str = Field(default="", description="简短描述")
    source: SourceType = Field(..., description="来源类型")
    install_root: str = Field(..., description="安装根目录")
    upstream_key: str = Field(..., description="mcpServers 中的原始 key")
    transport: TransportType = Field(..., description="传输类型")
    default_disabled: bool = Field(default=False, description="默认禁用")
    default_config: NormalizedConfig = Field(..., description="默认配置")
    diagnostics: Diagnostics = Field(default_factory=Diagnostics, description="诊断信息")

    # RPM 元数据（可选）
    rpm_metadata: dict[str, Any] = Field(default_factory=dict, description="RPM 元数据")

    model_config = {"frozen": False}  # 允许修改


class Override(BaseModel):
    """覆盖配置

    支持全局和用户级配置覆盖，不修改原始安装目录
    """

    scope: str = Field(..., description="作用域：global 或 user/<user_id>")
    disabled: bool | None = Field(default=None, description="是否禁用")
    env: dict[str, str] = Field(default_factory=dict, description="环境变量覆盖")
    headers: dict[str, str] = Field(default_factory=dict, description="请求头覆盖")
    timeouts: Timeouts | None = Field(default=None, description="超时覆盖")
    concurrency: Concurrency | None = Field(default=None, description="并发覆盖")
    arg_patches: list[dict[str, Any]] = Field(default_factory=list, description="参数补丁")


class RuntimeState(BaseModel):
    """运行时状态

    记录 MCP Session 的运行时信息
    """

    user_id: str = Field(..., description="用户 ID")
    mcp_id: str = Field(..., description="MCP Server ID")
    pid: int | None = Field(default=None, description="进程 ID")
    started_at: datetime | None = Field(default=None, description="启动时间")
    last_used_at: datetime | None = Field(default=None, description="最后使用时间")
    restart_count: int = Field(default=0, description="重启次数")
    status: str = Field(default="stopped", description="状态：starting/running/stopped/error")
    last_error: str | None = Field(default=None, description="最后错误")

    @property
    def session_key(self) -> str:
        """会话唯一键"""
        return f"{self.user_id}:{self.mcp_id}"

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self.status == "running"
