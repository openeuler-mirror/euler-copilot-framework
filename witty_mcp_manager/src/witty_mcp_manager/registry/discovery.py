"""
MCP Server 发现模块

扫描 RPM 安装目录和管理员配置，生成 ServerRecord 列表
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from witty_mcp_manager.registry.models import (
    NormalizedConfig,
    ServerRecord,
    SourceType,
    SseConfig,
    Timeouts,
    ToolPolicy,
    TransportType,
)
from witty_mcp_manager.registry.normalizer import Normalizer

if TYPE_CHECKING:
    from witty_mcp_manager.config.config import AdminSource, ManagerConfig

logger = logging.getLogger(__name__)


class Discovery:
    """
    MCP Server 发现服务

    负责扫描和发现所有 MCP Server：
    1. RPM 生态 MCP（/opt/mcp-servers/servers）
    2. 管理员配置的 MCP（admin_sources）
    """

    def __init__(self, config: ManagerConfig) -> None:
        """
        初始化发现服务

        Args:
            config: 管理器配置

        """
        self.config = config
        self.normalizer = Normalizer()

    def scan_all(self) -> list[ServerRecord]:
        """
        扫描所有来源的 MCP Servers

        Returns:
            ServerRecord 列表

        """
        servers: list[ServerRecord] = []

        # 1. 扫描 RPM 安装目录
        for scan_path in self.config.scan_paths:
            rpm_servers = self._scan_rpm_path(scan_path)
            servers.extend(rpm_servers)
            logger.info("Found %d RPM servers in %s", len(rpm_servers), scan_path)

        # 2. 注册 admin sources
        for admin_source in self.config.admin_sources:
            server = self._create_admin_server(admin_source)
            if server:
                servers.append(server)
                logger.info("Registered admin source: %s", admin_source.id)

        logger.info("Total servers discovered: %d", len(servers))
        return servers

    def _scan_rpm_path(self, base_path: str) -> list[ServerRecord]:
        """
        扫描 RPM 安装路径

        Args:
            base_path: 扫描根目录

        Returns:
            ServerRecord 列表

        """
        servers: list[ServerRecord] = []
        base = Path(base_path)

        if not base.exists():
            logger.warning("Scan path does not exist: %s", base_path)
            return servers

        if not base.is_dir():
            logger.warning("Scan path is not a directory: %s", base_path)
            return servers

        for server_dir in base.iterdir():
            if not server_dir.is_dir():
                continue

            # 跳过隐藏目录
            if server_dir.name.startswith("."):
                continue

            try:
                server = self._parse_server_dir(server_dir)
                if server:
                    servers.append(server)
            except Exception:
                # 单个解析失败不影响其他（目录内容可能不受控）
                logger.exception("Failed to parse %s", server_dir)

        return servers

    def _parse_server_dir(self, server_dir: Path) -> ServerRecord | None:
        """
        解析单个 server 目录

        支持两种配置文件名：
        - mcp_config.json（RPM 标准格式）
        - config.json（mcp_center 格式）

        Args:
            server_dir: server 目录路径

        Returns:
            ServerRecord 或 None

        """
        # 支持多种配置文件名
        config_file = None
        for filename in ("mcp_config.json", "config.json"):
            candidate = server_dir / filename
            if candidate.exists():
                config_file = candidate
                break

        if config_file is None:
            logger.debug("No mcp_config.json or config.json in %s", server_dir)
            return None

        # 解析配置文件
        try:
            with config_file.open(encoding="utf-8") as f:
                raw_config = json.load(f)
        except json.JSONDecodeError:
            logger.exception("Invalid JSON in %s", config_file)
            return None

        # 解析 mcp-rpm.yaml（可选，仅 RPM 包有）
        rpm_yaml = server_dir / "mcp-rpm.yaml"
        rpm_metadata: dict[str, Any] = {}
        if rpm_yaml.exists():
            try:
                with rpm_yaml.open(encoding="utf-8") as f:
                    rpm_metadata = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                logger.warning("Invalid YAML in %s: %s", rpm_yaml, e)

        # 根据目录来源确定 source type
        # mcp_center 目录通常在 /usr/lib/sysagent/mcp_center/mcp_config/
        source = SourceType.RPM
        if "mcp_center" in str(server_dir) or config_file.name == "config.json":
            source = SourceType.ADMIN

        # 标准化配置
        return self.normalizer.normalize(
            server_dir=server_dir,
            raw_config=raw_config,
            rpm_metadata=rpm_metadata,
            source=source,
        )

    def _create_admin_server(self, admin_source: AdminSource) -> ServerRecord | None:
        """
        从 admin source 创建 ServerRecord

        Args:
            admin_source: 管理员配置的 MCP 源

        Returns:
            ServerRecord 或 None

        """
        try:
            transport = TransportType(admin_source.transport)

            # 构建配置
            stdio_config = None
            sse_config = None

            if transport == TransportType.SSE and admin_source.sse:
                sse_config = SseConfig(
                    url=admin_source.sse.get("url", ""),
                    headers=admin_source.sse.get("headers", {}),
                    timeout=admin_source.sse.get("timeout", 60),
                )

            normalized_config = NormalizedConfig(
                transport=transport,
                stdio=stdio_config,
                sse=sse_config,
                tool_policy=ToolPolicy(),
                timeouts=Timeouts(),
                extras={},
            )

            return ServerRecord(
                id=admin_source.id,
                name=admin_source.name,
                summary=admin_source.description,
                source=SourceType.ADMIN,
                install_root=admin_source.source_path or "",
                upstream_key=admin_source.id,
                transport=transport,
                default_disabled=admin_source.default_disabled,
                default_config=normalized_config,
            )
        except Exception:
            logger.exception("Failed to create admin server %s", admin_source.id)
            return None

    def get_server_by_id(self, server_id: str) -> ServerRecord | None:
        """
        根据 ID 获取 ServerRecord

        Args:
            server_id: Server ID

        Returns:
            ServerRecord 或 None

        """
        servers = self.scan_all()
        for server in servers:
            if server.id == server_id:
                return server
        return None
