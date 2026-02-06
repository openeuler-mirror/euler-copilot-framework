"""Witty MCP Manager 配置加载模块"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AdminSource(BaseModel):
    """管理员配置的 MCP 源"""

    id: str = Field(..., description="唯一标识")
    name: str = Field(..., description="显示名称")
    transport: str = Field(..., description="传输类型：stdio/sse/streamable_http")
    sse: dict[str, Any] | None = Field(default=None, description="SSE 配置")
    stdio: dict[str, Any] | None = Field(default=None, description="STDIO 配置")
    default_disabled: bool = Field(default=False, description="默认禁用")
    description: str = Field(default="", description="描述")
    source_path: str | None = Field(default=None, description="源码路径")


class ManagerConfig(BaseModel):
    """Witty MCP Manager 配置"""

    # 扫描路径
    scan_paths: list[str] = Field(
        default_factory=lambda: [
            "/opt/mcp-servers/servers",
            "/usr/lib/sysagent/mcp_center/mcp_config",
        ],
        description="MCP 安装目录扫描路径",
    )

    # 目录配置
    state_directory: str = Field(
        default="/var/lib/witty-mcp-manager",
        description="状态数据目录",
    )
    runtime_directory: str = Field(
        default="/run/witty",
        description="运行时目录",
    )
    socket_path: str = Field(
        default="/run/witty/mcp-manager.sock",
        description="UDS socket 路径",
    )

    # 管理员配置的 MCP 源
    admin_sources: list[AdminSource] = Field(
        default_factory=list,
        description="管理员配置的 MCP 源",
    )

    # 安全配置
    command_allowlist: list[str] = Field(
        default_factory=lambda: ["uv", "python3", "python", "node", "npx"],
        description="允许的启动命令",
    )

    # 性能配置
    tools_cache_ttl: int = Field(default=600, description="Tools 缓存 TTL（秒）")
    idle_session_ttl: int = Field(default=600, description="空闲会话 TTL（秒）")
    max_restart_attempts: int = Field(default=3, description="最大重启次数")

    # 并发配置
    max_concurrent_per_user: int = Field(default=5, description="每用户最大并发")
    max_concurrent_global: int = Field(default=100, description="全局最大并发")

    # 超时配置
    default_tool_call_timeout: int = Field(default=30, description="默认 Tool 调用超时（秒）")
    default_connect_timeout: int = Field(default=10, description="默认连接超时（秒）")


def load_config(config_path: str | None = None) -> ManagerConfig:
    """
    加载配置文件

    配置文件搜索顺序：
    1. 显式指定的路径
    2. 环境变量 WITTY_MCP_CONFIG
    3. /etc/witty/mcp-manager.yaml
    4. ~/.config/witty/mcp-manager.yaml

    Args:
        config_path: 显式指定的配置文件路径

    Returns:
        ManagerConfig 实例

    """
    paths_to_try = [
        config_path,
        os.environ.get("WITTY_MCP_CONFIG"),
        "/etc/witty/mcp-manager.yaml",
        str(Path.home() / ".config/witty/mcp-manager.yaml"),
    ]

    for path in paths_to_try:
        if path and Path(path).exists():
            logger.info("Loading config from: %s", path)
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) or {}
                return ManagerConfig(**data)
            except Exception:
                logger.exception("Failed to load config from %s", path)
                continue

    logger.info("No config file found, using defaults")
    return ManagerConfig()


# 全局配置实例
_config: ManagerConfig | None = None


def get_config() -> ManagerConfig:
    """
    获取全局配置实例

    Returns:
        全局 ManagerConfig 实例

    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """重置全局配置（主要用于测试）"""
    global _config
    _config = None
