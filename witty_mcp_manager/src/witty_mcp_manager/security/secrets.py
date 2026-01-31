"""
Secrets 管理模块

支持通过引用（而非明文）管理敏感配置，如 API Key、Token 等。
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from witty_mcp_manager.exceptions import ConfigError

logger = logging.getLogger(__name__)


class SecretsManager:
    """
    Secrets 管理器

    支持的引用格式：
    - ${env:VAR_NAME}: 从环境变量读取
    - ${file:/path/to/secret}: 从文件读取
    - ${secrets:key_name}: 从 secrets 目录读取

    目录结构:
        {state_directory}/
        └── secrets/
            └── {key_name}  # 单文件存储单个 secret
    """

    # 引用模式
    REF_PATTERN = re.compile(r"\$\{(\w+):([^}]+)\}")

    def __init__(self, state_directory: str | Path) -> None:
        """
        初始化管理器

        Args:
            state_directory: StateDirectory 路径

        """
        self.state_directory = Path(state_directory)
        self.secrets_dir = self.state_directory / "secrets"

    def ensure_directory(self) -> None:
        """确保 secrets 目录存在"""
        self.secrets_dir.mkdir(parents=True, exist_ok=True)
        # 设置严格权限（仅 owner 可读写）
        self.secrets_dir.chmod(0o700)
        logger.debug("Secrets directory ensured: %s", self.secrets_dir)

    def is_reference(self, value: str) -> bool:
        """
        检查值是否为引用

        Args:
            value: 值

        Returns:
            是否为引用

        """
        return isinstance(value, str) and self.REF_PATTERN.search(value) is not None

    def resolve_reference(self, reference: str) -> str:
        """
        解析引用

        Args:
            reference: 引用字符串（如 ${env:API_KEY}）

        Returns:
            解析后的值

        Raises:
            ConfigError: 解析失败

        """
        match = self.REF_PATTERN.match(reference)
        if not match:
            return reference

        ref_type = match.group(1)
        ref_key = match.group(2)

        if ref_type == "env":
            return self._resolve_env(ref_key)
        if ref_type == "file":
            return self._resolve_file(ref_key)
        if ref_type == "secrets":
            return self._resolve_secrets(ref_key)
        msg = f"Unknown secret reference type: {ref_type}"
        raise ConfigError(msg)

    def _resolve_env(self, var_name: str) -> str:
        """从环境变量解析"""
        value = os.environ.get(var_name)
        if value is None:
            msg = f"Environment variable not found: {var_name}"
            raise ConfigError(msg)
        return value

    def _resolve_file(self, file_path: str) -> str:
        """从文件解析"""
        path = Path(file_path)
        if not path.exists():
            msg = f"Secret file not found: {file_path}"
            raise ConfigError(msg)
        if not path.is_file():
            msg = f"Secret path is not a file: {file_path}"
            raise ConfigError(msg)

        try:
            return path.read_text().strip()
        except OSError as e:
            msg = f"Failed to read secret file {file_path}: {e}"
            raise ConfigError(msg) from e

    def _resolve_secrets(self, key_name: str) -> str:
        """从 secrets 目录解析"""
        secret_path = self.secrets_dir / key_name
        if not secret_path.exists():
            msg = f"Secret not found: {key_name}"
            raise ConfigError(msg)

        try:
            return secret_path.read_text().strip()
        except OSError as e:
            msg = f"Failed to read secret {key_name}: {e}"
            raise ConfigError(msg) from e

    def resolve_all(self, value: str) -> str:
        """
        解析值中的所有引用

        Args:
            value: 可能包含引用的字符串

        Returns:
            解析后的字符串

        """

        def replace_ref(match: re.Match[str]) -> str:
            full_ref = match.group(0)
            try:
                return self.resolve_reference(full_ref)
            except ConfigError as e:
                logger.warning("Failed to resolve reference %s: %s", full_ref, e)
                return full_ref

        return self.REF_PATTERN.sub(replace_ref, value)

    def resolve_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        解析字典中的所有引用

        Args:
            data: 原始字典

        Returns:
            解析后的字典

        """
        result: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.resolve_all(value)
            elif isinstance(value, dict):
                result[key] = self.resolve_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self.resolve_all(v) if isinstance(v, str) else self.resolve_dict(v) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                result[key] = value
        return result

    def save_secret(self, key_name: str, value: str) -> Path:
        """
        保存 secret

        Args:
            key_name: secret 名称
            value: secret 值

        Returns:
            保存的文件路径

        """
        self.ensure_directory()

        # 验证 key_name（防止路径穿越）
        if "/" in key_name or "\\" in key_name or ".." in key_name:
            msg = f"Invalid secret key name: {key_name}"
            raise ConfigError(msg)

        secret_path = self.secrets_dir / key_name

        try:
            secret_path.write_text(value)
            secret_path.chmod(0o600)  # 仅 owner 可读写

        except OSError as e:
            msg = f"Failed to save secret {key_name}: {e}"
            raise ConfigError(msg) from e

        else:
            logger.info("Saved secret: %s", key_name)
            return secret_path

    def delete_secret(self, key_name: str) -> bool:
        """
        删除 secret

        Args:
            key_name: secret 名称

        Returns:
            是否删除成功

        """
        secret_path = self.secrets_dir / key_name

        if not secret_path.exists():
            return False

        try:
            secret_path.unlink()

        except OSError as e:
            logger.warning("Failed to delete secret %s: %s", key_name, e)
            return False

        else:
            logger.info("Deleted secret: %s", key_name)
            return True

    def list_secrets(self) -> list[str]:
        """
        列出所有 secret 名称

        Returns:
            secret 名称列表（不包含值）

        """
        if not self.secrets_dir.exists():
            return []

        return [p.name for p in self.secrets_dir.iterdir() if p.is_file()]

    def has_secret(self, key_name: str) -> bool:
        """
        检查 secret 是否存在

        Args:
            key_name: secret 名称

        Returns:
            是否存在

        """
        secret_path = self.secrets_dir / key_name
        return secret_path.exists() and secret_path.is_file()
