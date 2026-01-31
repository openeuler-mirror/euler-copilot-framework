"""
预检查模块

在启动 MCP Server 前进行命令白名单、依赖检查
"""

from __future__ import annotations

import logging
import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from witty_mcp_manager.config.config import ManagerConfig
    from witty_mcp_manager.registry.models import Diagnostics, ServerRecord

logger = logging.getLogger(__name__)


class PreflightChecker:
    """
    预检查器

    执行启动前检查：
    1. 命令白名单检查
    2. 命令存在性检查
    3. 依赖检查
    """

    def __init__(self, config: ManagerConfig) -> None:
        """
        初始化预检查器

        Args:
            config: 管理器配置

        """
        self.config = config

    def check_command_allowlist(self, command: str) -> bool:
        """
        检查命令是否在白名单中

        Args:
            command: 命令名

        Returns:
            是否允许

        """
        return command in self.config.command_allowlist

    def check_command_exists(self, command: str) -> bool:
        """
        检查命令是否存在

        Args:
            command: 命令名

        Returns:
            是否存在

        """
        return shutil.which(command) is not None

    def check_dependencies(self, server: ServerRecord) -> dict[str, list[str]]:
        """
        检查依赖

        Args:
            server: ServerRecord

        Returns:
            缺失依赖字典 {"system": [...], "python": [...], "packages": [...]}

        """
        missing: dict[str, list[str]] = {
            "system": [],
            "python": [],
            "packages": [],
        }

        rpm_metadata = server.rpm_metadata
        if not rpm_metadata:
            return missing

        dependencies = rpm_metadata.get("dependencies", {})

        # 检查系统依赖
        for dep in dependencies.get("system", []):
            if not shutil.which(dep):
                missing["system"].append(dep)

        # 检查 packages（如 git, jq）
        for dep in dependencies.get("packages", []):
            if not shutil.which(dep):
                missing["packages"].append(dep)

        # Python 依赖检查（简化版，只检查是否可 import）
        # 完整检查需要在目标环境中执行
        # 这里暂时跳过

        return missing

    def generate_suggestions(self, missing_deps: dict[str, list[str]]) -> list[str]:
        """
        生成修复建议

        Args:
            missing_deps: 缺失依赖

        Returns:
            建议列表

        """
        suggestions: list[str] = []

        if missing_deps.get("system"):
            deps = " ".join(missing_deps["system"])
            suggestions.append(f"Install system dependencies: dnf install {deps}")

        if missing_deps.get("packages"):
            deps = " ".join(missing_deps["packages"])
            suggestions.append(f"Install packages: dnf install {deps}")

        if missing_deps.get("python"):
            deps = " ".join(missing_deps["python"])
            suggestions.append(f"Install Python packages: pip install {deps}")

        return suggestions

    def run_preflight(self, server: ServerRecord) -> Diagnostics:
        """
        运行预检查

        Args:
            server: ServerRecord

        Returns:
            更新后的 Diagnostics

        """
        diagnostics = server.diagnostics.model_copy()

        # 检查 STDIO 命令
        if server.default_config.stdio:
            command = server.default_config.stdio.command

            # 白名单检查
            if not self.check_command_allowlist(command):
                diagnostics.command_allowed = False
                diagnostics.errors.append(
                    f"Command '{command}' is not in allowlist. Allowed: {', '.join(self.config.command_allowlist)}"
                )

            # 存在性检查
            if not self.check_command_exists(command):
                diagnostics.command_exists = False
                diagnostics.warnings.append(f"Command '{command}' not found in PATH")

        # 依赖检查
        missing_deps = self.check_dependencies(server)
        diagnostics.deps_missing = missing_deps

        # 生成建议
        if any(missing_deps.values()):
            suggestions = self.generate_suggestions(missing_deps)
            diagnostics.suggestions.extend(suggestions)

            # 依赖缺失作为警告（不阻止启动）
            for dep_type, deps in missing_deps.items():
                if deps:
                    diagnostics.warnings.append(f"Missing {dep_type} dependencies: {', '.join(deps)}")

        return diagnostics
