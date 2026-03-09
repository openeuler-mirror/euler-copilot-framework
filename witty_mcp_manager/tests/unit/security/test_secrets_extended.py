"""SecretsManager 补充单元测试

覆盖 security/secrets.py 中未测试的分支和边界条件。
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from witty_mcp_manager.exceptions import ConfigError
from witty_mcp_manager.security.secrets import SecretsManager

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def secrets_manager(tmp_path: Path) -> SecretsManager:
    """创建 SecretsManager 实例"""
    return SecretsManager(tmp_path)


class TestSecretsManagerExtended:
    """SecretsManager 补充测试"""

    def test_unknown_ref_type_raises(self, secrets_manager: SecretsManager) -> None:
        """测试未知引用类型抛出 ConfigError"""
        with pytest.raises(ConfigError, match="Unknown secret reference type"):
            secrets_manager.resolve_reference("${unknown:value}")

    def test_resolve_reference_non_ref_returns_unchanged(self, secrets_manager: SecretsManager) -> None:
        """测试非引用字符串直接返回"""
        result = secrets_manager.resolve_reference("plain_value")
        assert result == "plain_value"

    def test_resolve_file_not_a_file(self, secrets_manager: SecretsManager, tmp_path: Path) -> None:
        """测试路径存在但不是文件"""
        dir_path = tmp_path / "not_a_file"
        dir_path.mkdir()
        with pytest.raises(ConfigError, match="not a file"):
            secrets_manager.resolve_reference(f"${{file:{dir_path}}}")

    def test_resolve_file_read_error(self, secrets_manager: SecretsManager, tmp_path: Path) -> None:
        """测试文件读取 OS 错误"""
        secret_file = tmp_path / "unreadable.txt"
        secret_file.write_text("secret")
        secret_file.chmod(0o000)
        try:
            with pytest.raises(ConfigError, match="Failed to read secret file"):
                secrets_manager.resolve_reference(f"${{file:{secret_file}}}")
        finally:
            secret_file.chmod(0o644)

    def test_resolve_secrets_read_error(self, secrets_manager: SecretsManager) -> None:
        """测试 secrets 目录中的文件读取错误"""
        secrets_manager.ensure_directory()
        secret_path = secrets_manager.secrets_dir / "bad_key"
        secret_path.write_text("value")
        secret_path.chmod(0o000)
        try:
            with pytest.raises(ConfigError, match="Failed to read secret"):
                secrets_manager.resolve_reference("${secrets:bad_key}")
        finally:
            secret_path.chmod(0o644)

    def test_resolve_secrets_not_found(self, secrets_manager: SecretsManager) -> None:
        """测试 secrets 引用不存在"""
        secrets_manager.ensure_directory()
        with pytest.raises(ConfigError, match="Secret not found"):
            secrets_manager.resolve_reference("${secrets:nonexistent}")

    def test_resolve_all_failed_ref_kept(self, secrets_manager: SecretsManager) -> None:
        """测试解析失败的引用保留原值"""
        result = secrets_manager.resolve_all("prefix-${env:DEFINITELY_NOT_SET}-suffix")
        assert "${env:DEFINITELY_NOT_SET}" in result

    def test_resolve_dict_nested_list(self, secrets_manager: SecretsManager) -> None:
        """测试嵌套列表中的引用解析"""
        with patch.dict(os.environ, {"K": "V"}):
            data = {
                "list": ["${env:K}", {"inner": "${env:K}"}, 42],
            }
            result = secrets_manager.resolve_dict(data)
            assert result["list"][0] == "V"
            assert result["list"][1]["inner"] == "V"
            assert result["list"][2] == 42

    def test_resolve_dict_non_string_values(self, secrets_manager: SecretsManager) -> None:
        """测试非字符串值不做处理"""
        data = {
            "count": 42,
            "enabled": True,
            "ratio": 3.14,
            "empty": None,
        }
        result = secrets_manager.resolve_dict(data)
        assert result == data

    def test_is_reference_non_string(self, secrets_manager: SecretsManager) -> None:
        """测试非字符串输入返回 False"""
        assert secrets_manager.is_reference(42) is False  # type: ignore[arg-type]

    def test_save_secret_backslash_name(self, secrets_manager: SecretsManager) -> None:
        """测试包含反斜杠的 key 名称"""
        with pytest.raises(ConfigError, match="Invalid secret key name"):
            secrets_manager.save_secret("path\\evil", "val")

    def test_save_secret_dotdot_name(self, secrets_manager: SecretsManager) -> None:
        """测试包含 .. 的 key 名称"""
        with pytest.raises(ConfigError, match="Invalid secret key name"):
            secrets_manager.save_secret("..key", "val")

    def test_list_secrets_no_dir(self, secrets_manager: SecretsManager) -> None:
        """测试 secrets 目录不存在时返回空"""
        assert secrets_manager.list_secrets() == []

    def test_has_secret_false(self, secrets_manager: SecretsManager) -> None:
        """测试 secret 不存在"""
        assert secrets_manager.has_secret("nonexistent") is False

    def test_has_secret_true(self, secrets_manager: SecretsManager) -> None:
        """测试 secret 存在"""
        secrets_manager.save_secret("exists", "val")
        assert secrets_manager.has_secret("exists") is True

    def test_has_secret_directory(self, secrets_manager: SecretsManager) -> None:
        """测试同名目录不算 secret"""
        secrets_manager.ensure_directory()
        (secrets_manager.secrets_dir / "dir_name").mkdir()
        assert secrets_manager.has_secret("dir_name") is False

    def test_delete_secret_os_error(self, secrets_manager: SecretsManager) -> None:
        """测试删除时的 OS 错误返回 False"""
        secrets_manager.save_secret("protected", "val")
        # 目录设为只读使删除失败
        secrets_manager.secrets_dir.chmod(0o500)
        try:
            result = secrets_manager.delete_secret("protected")
            assert result is False
        finally:
            secrets_manager.secrets_dir.chmod(0o700)

    def test_save_secret_os_error(self, secrets_manager: SecretsManager) -> None:
        """测试保存时写入失败"""
        secrets_manager.ensure_directory()
        with (
            patch.object(
                type(secrets_manager.secrets_dir / "x"),
                "write_text",
                side_effect=OSError("disk full"),
            ),
            pytest.raises(ConfigError, match="Failed to save secret"),
        ):
            secrets_manager.save_secret("test_key", "value")

    def test_ensure_directory_permissions(self, secrets_manager: SecretsManager) -> None:
        """测试 ensure_directory 设置 700 权限"""
        secrets_manager.ensure_directory()
        mode = secrets_manager.secrets_dir.stat().st_mode & 0o777
        assert mode == 0o700
