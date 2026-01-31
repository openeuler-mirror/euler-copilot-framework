"""
Overlay 持久化存储模块

负责将覆盖配置持久化到 StateDirectory（/var/lib/witty-mcp-manager）。
支持全局（global）和用户级（user/<user_id>）两层配置。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from witty_mcp_manager.exceptions import ConfigError
from witty_mcp_manager.registry.models import Override

logger = logging.getLogger(__name__)


class OverlayStorage:
    """
    Overlay 持久化存储

    目录结构:
        {state_directory}/
        └── overrides/
            ├── global/
            │   └── {mcp_id}.json
            └── users/
                └── {user_id}/
                    └── {mcp_id}.json
    """

    def __init__(self, state_directory: str | Path) -> None:
        """
        初始化存储

        Args:
            state_directory: StateDirectory 路径（通常为 /var/lib/witty-mcp-manager）

        """
        self.state_directory = Path(state_directory)
        self.overrides_dir = self.state_directory / "overrides"
        self.global_dir = self.overrides_dir / "global"
        self.users_dir = self.overrides_dir / "users"

    def ensure_directories(self) -> None:
        """确保目录结构存在"""
        self.global_dir.mkdir(parents=True, exist_ok=True)
        self.users_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("Overlay directories ensured: %s", self.overrides_dir)

    def _get_override_path(self, mcp_id: str, user_id: str | None = None) -> Path:
        """
        获取 override 文件路径

        Args:
            mcp_id: MCP Server ID
            user_id: 用户 ID（None 表示全局配置）

        Returns:
            override 文件路径

        """
        if user_id:
            user_dir = self.users_dir / user_id
            return user_dir / f"{mcp_id}.json"
        return self.global_dir / f"{mcp_id}.json"

    def save_override(
        self,
        mcp_id: str,
        override: Override,
        user_id: str | None = None,
    ) -> Path:
        """
        保存覆盖配置

        Args:
            mcp_id: MCP Server ID
            override: 覆盖配置
            user_id: 用户 ID（None 表示全局配置）

        Returns:
            保存的文件路径

        Raises:
            ConfigError: 保存失败

        """
        file_path = self._get_override_path(mcp_id, user_id)

        try:
            # 确保父目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入 JSON 文件
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(override.model_dump(exclude_none=True), f, indent=2, ensure_ascii=False)

        except OSError as e:
            msg = f"Failed to save override for {mcp_id}: {e}"
            logger.exception(msg)
            raise ConfigError(msg) from e

        else:
            scope = f"user/{user_id}" if user_id else "global"
            logger.info("Saved override for %s (scope=%s): %s", mcp_id, scope, file_path)
            return file_path

    def load_override(self, mcp_id: str, user_id: str | None = None) -> Override | None:
        """
        加载覆盖配置

        Args:
            mcp_id: MCP Server ID
            user_id: 用户 ID（None 表示全局配置）

        Returns:
            覆盖配置，不存在则返回 None

        """
        file_path = self._get_override_path(mcp_id, user_id)

        if not file_path.exists():
            return None

        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # 如果文件中没有 scope，则设置默认值
            if "scope" not in data:
                data["scope"] = f"user/{user_id}" if user_id else "global"
            return Override(**data)

        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to load override from %s: %s", file_path, e)
            return None

    def delete_override(self, mcp_id: str, user_id: str | None = None) -> bool:
        """
        删除覆盖配置

        Args:
            mcp_id: MCP Server ID
            user_id: 用户 ID（None 表示全局配置）

        Returns:
            是否删除成功

        """
        file_path = self._get_override_path(mcp_id, user_id)

        if not file_path.exists():
            return False

        try:
            file_path.unlink()

        except OSError as e:
            logger.warning("Failed to delete override %s: %s", file_path, e)
            return False

        else:
            scope = f"user/{user_id}" if user_id else "global"
            logger.info("Deleted override for %s (scope=%s)", mcp_id, scope)
            return True

    def list_global_overrides(self) -> list[str]:
        """
        列出所有全局覆盖配置的 MCP ID

        Returns:
            MCP ID 列表

        """
        if not self.global_dir.exists():
            return []

        return [p.stem for p in self.global_dir.glob("*.json")]

    def list_user_overrides(self, user_id: str) -> list[str]:
        """
        列出用户的所有覆盖配置的 MCP ID

        Args:
            user_id: 用户 ID

        Returns:
            MCP ID 列表

        """
        user_dir = self.users_dir / user_id
        if not user_dir.exists():
            return []

        return [p.stem for p in user_dir.glob("*.json")]

    def list_all_users(self) -> list[str]:
        """
        列出所有有覆盖配置的用户 ID

        Returns:
            用户 ID 列表

        """
        if not self.users_dir.exists():
            return []

        return [d.name for d in self.users_dir.iterdir() if d.is_dir()]

    def is_globally_disabled(self, mcp_id: str) -> bool:
        """
        检查 MCP 是否被全局禁用

        Args:
            mcp_id: MCP Server ID

        Returns:
            是否被全局禁用

        """
        override = self.load_override(mcp_id)
        return override is not None and override.disabled is True

    def is_user_enabled(self, mcp_id: str, user_id: str) -> bool | None:
        """
        检查用户是否启用了 MCP

        Args:
            mcp_id: MCP Server ID
            user_id: 用户 ID

        Returns:
            True=启用, False=禁用, None=未设置

        """
        override = self.load_override(mcp_id, user_id)
        if override is None:
            return None
        # disabled=False 表示启用，disabled=True 表示禁用
        if override.disabled is None:
            return None
        return not override.disabled
