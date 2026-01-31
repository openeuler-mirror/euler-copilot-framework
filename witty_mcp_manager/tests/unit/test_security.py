"""
Security 模块单元测试
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from witty_mcp_manager.exceptions import CommandNotAllowedError, ConfigError
from witty_mcp_manager.security.allowlist import CommandAllowlist
from witty_mcp_manager.security.redaction import LogRedactor, get_redactor, redact
from witty_mcp_manager.security.secrets import SecretsManager


class TestCommandAllowlist:
    """CommandAllowlist 测试"""

    def test_default_allowed_commands(self) -> None:
        """测试默认允许的命令"""
        allowlist = CommandAllowlist()

        assert allowlist.is_allowed("uv") is True
        assert allowlist.is_allowed("python3") is True
        assert allowlist.is_allowed("python") is True
        assert allowlist.is_allowed("node") is True
        assert allowlist.is_allowed("npx") is True
        assert allowlist.is_allowed("deno") is True

    def test_disallowed_commands(self) -> None:
        """测试不允许的命令"""
        allowlist = CommandAllowlist()

        assert allowlist.is_allowed("bash") is False
        assert allowlist.is_allowed("sh") is False
        assert allowlist.is_allowed("rm") is False
        assert allowlist.is_allowed("curl") is False

    def test_command_with_path(self) -> None:
        """测试带路径的命令"""
        allowlist = CommandAllowlist()

        assert allowlist.is_allowed("/usr/bin/python3") is True
        assert allowlist.is_allowed("/usr/local/bin/uv") is True
        assert allowlist.is_allowed("/bin/bash") is False

    def test_custom_allowed(self) -> None:
        """测试自定义白名单"""
        allowlist = CommandAllowlist(allowed={"custom_cmd"})

        assert allowlist.is_allowed("custom_cmd") is True
        assert allowlist.is_allowed("uv") is False  # 默认被覆盖

    def test_extra_allowed(self) -> None:
        """测试额外允许的命令"""
        allowlist = CommandAllowlist(extra_allowed={"custom_cmd"})

        assert allowlist.is_allowed("custom_cmd") is True
        assert allowlist.is_allowed("uv") is True  # 默认保留

    def test_check_raises_exception(self) -> None:
        """测试 check 方法抛出异常"""
        allowlist = CommandAllowlist()

        with pytest.raises(CommandNotAllowedError) as exc_info:
            allowlist.check("bash")

        assert "bash" in str(exc_info.value)

    def test_add_command(self) -> None:
        """测试添加命令"""
        allowlist = CommandAllowlist()

        allowlist.add("custom")
        assert allowlist.is_allowed("custom") is True

    def test_remove_command(self) -> None:
        """测试移除命令"""
        allowlist = CommandAllowlist()

        assert allowlist.remove("uv") is True
        assert allowlist.is_allowed("uv") is False

        # 移除不存在的
        assert allowlist.remove("nonexistent") is False

    def test_validate(self) -> None:
        """测试验证命令"""
        allowlist = CommandAllowlist()

        # 不允许的命令
        result = allowlist.validate("bash")
        assert result["allowed"] is False
        assert result["valid"] is False
        assert "error" in result

    @patch("shutil.which")
    def test_check_exists(self, mock_which) -> None:
        """测试检查命令存在性"""
        allowlist = CommandAllowlist()

        mock_which.return_value = "/usr/bin/python3"
        assert allowlist.check_exists("python3") is True

        mock_which.return_value = None
        assert allowlist.check_exists("nonexistent") is False


class TestLogRedactor:
    """LogRedactor 测试"""

    @pytest.fixture
    def redactor(self) -> LogRedactor:
        """创建脱敏器"""
        return LogRedactor()

    def test_sensitive_key_detection(self, redactor: LogRedactor) -> None:
        """测试敏感键检测"""
        assert redactor.is_sensitive_key("password") is True
        assert redactor.is_sensitive_key("api_key") is True
        assert redactor.is_sensitive_key("API_KEY") is True
        assert redactor.is_sensitive_key("secret_token") is True
        assert redactor.is_sensitive_key("name") is False
        assert redactor.is_sensitive_key("value") is False

    def test_redact_jwt_token(self, redactor: LogRedactor) -> None:
        """测试脱敏 JWT Token"""
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = redactor.redact_value(jwt)
        assert "eyJ" not in result
        assert "REDACTED" in result

    def test_redact_bearer_token(self, redactor: LogRedactor) -> None:
        """测试脱敏 Bearer Token"""
        header = "Bearer sk-1234567890abcdef"
        result = redactor.redact_value(header)
        assert "sk-" not in result
        assert "REDACTED" in result

    def test_redact_dict(self, redactor: LogRedactor) -> None:
        """测试脱敏字典"""
        data = {
            "username": "user1",
            "password": "secret123",
            "api_key": "key123",
            "normal": "value",
        }

        result = redactor.redact_dict(data)

        assert result["username"] == "user1"
        assert result["password"] == "***"
        assert result["api_key"] == "***"
        assert result["normal"] == "value"

    def test_redact_nested_dict(self, redactor: LogRedactor) -> None:
        """测试脱敏嵌套字典"""
        data = {
            "config": {
                "password": "secret",
                "nested": {
                    "token": "abc123",
                },
            },
        }

        result = redactor.redact_dict(data)

        assert result["config"]["password"] == "***"
        assert result["config"]["nested"]["token"] == "***"

    def test_redact_env(self, redactor: LogRedactor) -> None:
        """测试脱敏环境变量"""
        env = {
            "PATH": "/usr/bin",
            "API_KEY": "secret",
            "PASSWORD": "pass123",
        }

        result = redactor.redact_env(env)

        assert result["PATH"] == "/usr/bin"
        assert result["API_KEY"] == "***"
        assert result["PASSWORD"] == "***"

    def test_redact_headers(self, redactor: LogRedactor) -> None:
        """测试脱敏请求头"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer token123",
            "X-Api-Key": "key123",
        }

        result = redactor.redact_headers(headers)

        assert result["Content-Type"] == "application/json"
        assert result["Authorization"] == "***"
        assert result["X-Api-Key"] == "***"

    def test_extra_keywords(self) -> None:
        """测试额外关键词"""
        redactor = LogRedactor(extra_keywords={"custom_secret"})

        assert redactor.is_sensitive_key("custom_secret") is True
        assert redactor.is_sensitive_key("CUSTOM_SECRET") is True

    def test_global_redactor(self) -> None:
        """测试全局脱敏器"""
        result = redact({"password": "secret"})
        assert result["password"] == "***"


class TestSecretsManager:
    """SecretsManager 测试"""

    @pytest.fixture
    def temp_state_dir(self) -> Path:
        """创建临时 state 目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_state_dir: Path) -> SecretsManager:
        """创建管理器"""
        return SecretsManager(temp_state_dir)

    def test_is_reference(self, manager: SecretsManager) -> None:
        """测试引用检测"""
        assert manager.is_reference("${env:API_KEY}") is True
        assert manager.is_reference("${file:/path/to/secret}") is True
        assert manager.is_reference("${secrets:my_key}") is True
        assert manager.is_reference("plain_value") is False

    def test_resolve_env_reference(self, manager: SecretsManager) -> None:
        """测试解析环境变量引用"""
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            result = manager.resolve_reference("${env:TEST_VAR}")
            assert result == "test_value"

    def test_resolve_env_not_found(self, manager: SecretsManager) -> None:
        """测试解析不存在的环境变量"""
        with pytest.raises(ConfigError):
            manager.resolve_reference("${env:NONEXISTENT_VAR}")

    def test_resolve_file_reference(self, manager: SecretsManager, temp_state_dir: Path) -> None:
        """测试解析文件引用"""
        secret_file = temp_state_dir / "secret.txt"
        secret_file.write_text("file_secret")

        result = manager.resolve_reference(f"${{file:{secret_file}}}")
        assert result == "file_secret"

    def test_resolve_file_not_found(self, manager: SecretsManager) -> None:
        """测试解析不存在的文件"""
        with pytest.raises(ConfigError):
            manager.resolve_reference("${file:/nonexistent/path}")

    def test_resolve_secrets_reference(self, manager: SecretsManager) -> None:
        """测试解析 secrets 引用"""
        manager.save_secret("my_key", "my_secret")

        result = manager.resolve_reference("${secrets:my_key}")
        assert result == "my_secret"

    def test_resolve_all(self, manager: SecretsManager) -> None:
        """测试解析字符串中的所有引用"""
        with patch.dict(os.environ, {"HOST": "localhost", "PORT": "8080"}):
            result = manager.resolve_all("http://${env:HOST}:${env:PORT}")
            assert result == "http://localhost:8080"

    def test_resolve_dict(self, manager: SecretsManager) -> None:
        """测试解析字典中的引用"""
        with patch.dict(os.environ, {"API_KEY": "secret123"}):
            data = {
                "url": "http://example.com",
                "key": "${env:API_KEY}",
            }

            result = manager.resolve_dict(data)
            assert result["url"] == "http://example.com"
            assert result["key"] == "secret123"

    def test_save_and_load_secret(self, manager: SecretsManager) -> None:
        """测试保存和加载 secret"""
        manager.save_secret("test_key", "test_value")

        # 验证文件存在
        assert manager.has_secret("test_key") is True

        # 解析
        result = manager.resolve_reference("${secrets:test_key}")
        assert result == "test_value"

    def test_delete_secret(self, manager: SecretsManager) -> None:
        """测试删除 secret"""
        manager.save_secret("test_key", "test_value")

        assert manager.delete_secret("test_key") is True
        assert manager.has_secret("test_key") is False

        # 重复删除
        assert manager.delete_secret("test_key") is False

    def test_list_secrets(self, manager: SecretsManager) -> None:
        """测试列出 secrets"""
        manager.save_secret("key1", "value1")
        manager.save_secret("key2", "value2")

        secrets = manager.list_secrets()
        assert set(secrets) == {"key1", "key2"}

    def test_invalid_key_name(self, manager: SecretsManager) -> None:
        """测试无效的 key 名称"""
        with pytest.raises(ConfigError):
            manager.save_secret("../evil", "value")

        with pytest.raises(ConfigError):
            manager.save_secret("path/to/key", "value")
