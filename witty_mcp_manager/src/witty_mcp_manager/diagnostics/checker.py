"""
配置校验器模块

校验 MCP Server 配置的完整性和正确性
"""

from __future__ import annotations

import logging
import socket
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from witty_mcp_manager.registry.models import TransportType

if TYPE_CHECKING:
    from witty_mcp_manager.registry.models import Diagnostics, ServerRecord

logger = logging.getLogger(__name__)


class Checker:
    """
    配置校验器

    校验 MCP Server 配置的完整性
    """

    def check_files(self, server: ServerRecord) -> list[str]:
        """
        检查必要文件是否存在

        支持两种配置文件名：
        - mcp_config.json（RPM 标准格式）
        - config.json（mcp_center 格式，如 mcp_server_mcp、rag_mcp）

        Args:
            server: ServerRecord

        Returns:
            缺失文件列表

        """
        missing: list[str] = []
        install_root = Path(server.install_root)

        # 检查配置文件（支持两种文件名）
        has_config = (install_root / "mcp_config.json").exists() or (install_root / "config.json").exists()
        if not has_config:
            missing.append("mcp_config.json or config.json")

        # src/ 检查：缺失时记录为 warning，不影响 config_valid
        src_dir = install_root / "src"
        if not src_dir.exists():
            missing.append("src/")

        return missing

    def check_config_validity(self, server: ServerRecord) -> list[str]:
        """
        检查配置有效性

        Args:
            server: ServerRecord

        Returns:
            错误列表

        """
        errors: list[str] = []

        config = server.default_config

        # STDIO 配置检查
        if config.stdio and not config.stdio.command:
            errors.append("STDIO config missing command")

        # SSE 配置检查
        if config.sse and not config.sse.url:
            errors.append("SSE config missing url")

        # 传输类型与配置匹配检查

        if config.transport == TransportType.STDIO and not config.stdio:
            errors.append("Transport is STDIO but no stdio config provided")
        if config.transport == TransportType.SSE and not config.sse:
            errors.append("Transport is SSE but no sse config provided")

        return errors

    def check_sse_reachable(self, server: ServerRecord, *, log_failure: bool = True) -> bool | None:
        """
        TCP 级别探测 SSE/Streamable HTTP 后端是否可达（超时 3s）

        仅对 SSE / STREAMABLE_HTTP 传输有效，STDIO 返回 None。

        Args:
            server: ServerRecord
            log_failure: 不可达时是否记录 warning

        Returns:
            True=可达，False=不可达，None=不适用

        """
        config = server.default_config
        if config.transport not in (TransportType.SSE, TransportType.STREAMABLE_HTTP):
            return None

        url: str | None = None
        if config.sse:
            url = config.sse.url
        if not url:
            return None

        try:
            parsed = urlparse(url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            with socket.create_connection((host, port), timeout=3):
                return True
        except OSError:
            if log_failure:
                logger.warning("SSE/HTTP 后端不可达: %s → %s", server.id, url)
            return False

    def validate(self, server: ServerRecord) -> Diagnostics:
        """
        完整校验

        Args:
            server: ServerRecord

        Returns:
            更新后的 Diagnostics

        """
        diagnostics = server.diagnostics.model_copy()

        # 检查文件
        missing_files = self.check_files(server)
        # src/ 缺失仅作为 warning，不影响 config_valid
        critical_missing = [f for f in missing_files if f != "src/"]
        src_missing = "src/" in missing_files

        if critical_missing:
            diagnostics.errors.append(f"Missing files: {', '.join(critical_missing)}")
            diagnostics.config_valid = False
        if src_missing:
            diagnostics.warnings.append("Missing src/ directory")

        # 检查配置
        config_errors = self.check_config_validity(server)
        if config_errors:
            diagnostics.errors.extend(config_errors)
            diagnostics.config_valid = False

        # SSE/HTTP 后端可达性探测
        sse_reachable = self.check_sse_reachable(server)
        if sse_reachable is not None:
            diagnostics = diagnostics.model_copy(update={"sse_reachable": sse_reachable})

        return diagnostics
