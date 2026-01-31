"""
命令白名单模块

限制可执行的命令，防止恶意 MCP Server 执行危险操作。
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from witty_mcp_manager.exceptions import CommandNotAllowedError

logger = logging.getLogger(__name__)


class CommandAllowlist:
    """
    命令白名单

    默认允许的命令：
    - uv: Python 包管理器（RPM MCP 主要使用）
    - python3: Python 解释器
    - python: Python 解释器（兼容）
    - node: Node.js 运行时
    - npx: Node.js 包执行器
    - deno: Deno 运行时
    """

    DEFAULT_ALLOWED = frozenset(["uv", "python3", "python", "node", "npx", "deno"])

    def __init__(
        self,
        allowed: set[str] | None = None,
        extra_allowed: set[str] | None = None,
    ) -> None:
        """
        初始化白名单

        Args:
            allowed: 覆盖默认白名单（None 使用默认）
            extra_allowed: 额外允许的命令（追加到默认白名单）

        """
        if allowed is not None:
            self._allowed = set(allowed)
        else:
            self._allowed = set(self.DEFAULT_ALLOWED)

        if extra_allowed:
            self._allowed.update(extra_allowed)

        logger.debug("Command allowlist initialized: %s", self._allowed)

    @property
    def allowed_commands(self) -> frozenset[str]:
        """获取允许的命令列表"""
        return frozenset(self._allowed)

    def is_allowed(self, command: str) -> bool:
        """
        检查命令是否允许

        Args:
            command: 命令名称（可以是完整路径）

        Returns:
            是否允许

        """
        # 提取命令名称（去除路径）
        cmd_name = Path(command).name

        return cmd_name in self._allowed

    def check(self, command: str) -> None:
        """
        检查命令，不允许则抛出异常

        Args:
            command: 命令名称

        Raises:
            CommandNotAllowedError: 命令不在白名单中

        """
        if not self.is_allowed(command):
            raise CommandNotAllowedError(
                command=command,
                allowlist=list(self._allowed),
            )

    def add(self, command: str) -> None:
        """
        添加允许的命令

        Args:
            command: 命令名称

        """
        self._allowed.add(command)
        logger.info("Added command to allowlist: %s", command)

    def remove(self, command: str) -> bool:
        """
        移除允许的命令

        Args:
            command: 命令名称

        Returns:
            是否移除成功

        """
        if command in self._allowed:
            self._allowed.discard(command)
            logger.info("Removed command from allowlist: %s", command)
            return True
        return False

    def check_exists(self, command: str) -> bool:
        """
        检查命令是否存在于系统中

        Args:
            command: 命令名称

        Returns:
            命令是否存在

        """
        return shutil.which(command) is not None

    def validate(self, command: str) -> dict[str, Any]:
        """
        验证命令

        Args:
            command: 命令名称

        Returns:
            验证结果字典

        """
        cmd_name = Path(command).name
        allowed = self.is_allowed(command)
        exists = self.check_exists(cmd_name)

        result: dict[str, Any] = {
            "command": command,
            "command_name": cmd_name,
            "allowed": allowed,
            "exists": exists,
            "valid": allowed and exists,
        }

        if not allowed:
            result["error"] = f"Command '{cmd_name}' is not in allowlist"
            result["suggestion"] = f"Allowed commands: {', '.join(sorted(self._allowed))}"
        elif not exists:
            result["error"] = f"Command '{cmd_name}' not found in PATH"
            result["suggestion"] = f"Please install {cmd_name} or check your PATH"

        return result
