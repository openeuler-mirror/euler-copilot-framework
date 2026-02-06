"""
MCP 配置标准化模块

将不同格式的 mcp_config.json 转换为统一的 NormalizedConfig
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from witty_mcp_manager.registry.models import (
    Diagnostics,
    NormalizedConfig,
    ServerRecord,
    SourceType,
    SseConfig,
    StdioConfig,
    Timeouts,
    ToolPolicy,
    TransportType,
)

logger = logging.getLogger(__name__)


class Normalizer:
    """
    配置标准化器

    将 mcpServers 格式的配置转换为 ServerRecord
    """

    def normalize(
        self,
        server_dir: Path,
        raw_config: dict[str, Any],
        rpm_metadata: dict[str, Any] | None = None,
        source: SourceType = SourceType.RPM,
    ) -> ServerRecord | None:
        """
        标准化配置

        Args:
            server_dir: server 目录
            raw_config: mcp_config.json 原始内容
            rpm_metadata: mcp-rpm.yaml 内容（可选）
            source: 来源类型

        Returns:
            ServerRecord 或 None（解析失败时）

        """
        # 目录名作为 canonical id
        server_id = server_dir.name

        # 获取 mcpServers 配置
        mcp_servers = raw_config.get("mcpServers", {})
        if not mcp_servers:
            logger.warning("No mcpServers found in %s", server_dir)
            return None

        # 获取第一个（通常也是唯一一个）server 配置
        # upstream_key 可能与目录名不一致
        upstream_key = next(iter(mcp_servers.keys()))
        server_config = mcp_servers[upstream_key]

        # 确定传输类型
        transport = self._detect_transport(raw_config, server_config)

        # 构建标准化配置
        normalized_config = self._build_normalized_config(
            transport=transport,
            server_config=server_config,
            server_dir=server_dir,
            raw_config=raw_config,
        )

        # 构建诊断信息
        diagnostics = Diagnostics()

        # 构建 ServerRecord
        return ServerRecord(
            id=server_id,
            name=raw_config.get("name", server_id),
            summary=raw_config.get("description", rpm_metadata.get("summary", "") if rpm_metadata else ""),
            source=source,
            install_root=str(server_dir),
            upstream_key=upstream_key,
            transport=transport,
            default_disabled=server_config.get("disabled", False),
            default_config=normalized_config,
            diagnostics=diagnostics,
            rpm_metadata=rpm_metadata or {},
        )

    def _detect_transport(
        self,
        raw_config: dict[str, Any],
        server_config: dict[str, Any],
    ) -> TransportType:
        """
        检测传输类型

        Args:
            raw_config: 完整配置
            server_config: mcpServers 中的单个 server 配置

        Returns:
            TransportType

        """
        # 显式指定的 mcpType
        mcp_type = raw_config.get("mcpType", "").lower()
        if mcp_type == "sse":
            return TransportType.SSE
        if mcp_type in ("stdio", ""):
            # 默认或显式 stdio
            pass

        # 根据配置字段推断
        if "url" in server_config:
            return TransportType.SSE
        if "command" in server_config:
            return TransportType.STDIO

        # 默认 STDIO
        return TransportType.STDIO

    def _build_normalized_config(
        self,
        transport: TransportType,
        server_config: dict[str, Any],
        server_dir: Path,
        raw_config: dict[str, Any],
    ) -> NormalizedConfig:
        """
        构建标准化配置

        Args:
            transport: 传输类型
            server_config: server 配置
            server_dir: server 目录
            raw_config: 完整原始配置

        Returns:
            NormalizedConfig

        """
        stdio_config = None
        sse_config = None

        if transport == TransportType.STDIO:
            stdio_config = StdioConfig(
                command=server_config.get("command", "uv"),
                args=server_config.get("args", []),
                env=server_config.get("env", {}),
                cwd=str(server_dir),
            )
        elif transport == TransportType.SSE:
            sse_config = SseConfig(
                url=server_config.get("url", ""),
                headers=server_config.get("headers", {}),
                timeout=server_config.get("timeout", 60),
            )

        # Tool 策略
        tool_policy = ToolPolicy(
            cache_ttl=server_config.get("toolsCacheTtl", 600),
            auto_discover=server_config.get("autoDiscover", True),
            always_allow=server_config.get("alwaysAllow", []),
        )

        # 超时配置
        timeouts = Timeouts(
            tool_call=server_config.get("timeout", 30),
            connect=server_config.get("connectTimeout", 10),
            idle_ttl=server_config.get("idleTtl", 600),
        )

        # 收集未识别的字段到 extras
        known_keys = {
            "command",
            "args",
            "env",
            "url",
            "headers",
            "timeout",
            "disabled",
            "alwaysAllow",
            "autoDiscover",
            "toolsCacheTtl",
            "connectTimeout",
            "idleTtl",
        }
        extras = {k: v for k, v in server_config.items() if k not in known_keys}

        return NormalizedConfig(
            transport=transport,
            stdio=stdio_config,
            sse=sse_config,
            tool_policy=tool_policy,
            timeouts=timeouts,
            extras=extras,
        )
