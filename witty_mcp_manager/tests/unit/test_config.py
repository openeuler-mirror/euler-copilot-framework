"""config 模块单元测试

测试 ManagerConfig、AdminSource、load_config、get_config/reset_config。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import yaml

from witty_mcp_manager.config.config import (
    AdminSource,
    ManagerConfig,
    get_config,
    load_config,
    reset_config,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestAdminSource:
    """AdminSource 模型测试"""

    def test_basic_creation(self) -> None:
        """测试基本创建"""
        source = AdminSource(
            id="rag_mcp",
            name="RAG MCP",
            transport="sse",
            sse={"url": "http://127.0.0.1:12311/sse"},
        )
        assert source.id == "rag_mcp"
        assert source.name == "RAG MCP"
        assert source.transport == "sse"
        assert source.sse is not None

    def test_default_values(self) -> None:
        """测试默认值"""
        source = AdminSource(
            id="test",
            name="Test",
            transport="stdio",
        )
        assert source.default_disabled is False
        assert source.description == ""
        assert source.source_path is None
        assert source.sse is None
        assert source.stdio is None

    def test_disabled_source(self) -> None:
        """测试默认禁用的源"""
        source = AdminSource(
            id="test",
            name="Test",
            transport="sse",
            default_disabled=True,
        )
        assert source.default_disabled is True


class TestManagerConfig:
    """ManagerConfig 模型测试"""

    def test_default_config(self) -> None:
        """测试默认配置值"""
        config = ManagerConfig()
        assert len(config.scan_paths) == 2
        assert "/opt/mcp-servers/servers" in config.scan_paths
        assert config.state_directory == "/var/lib/witty-mcp-manager"
        assert config.runtime_directory == "/run/witty"
        assert config.socket_path == "/run/witty/mcp-manager.sock"
        assert config.tools_cache_ttl == 600
        assert config.idle_session_ttl == 600
        assert config.max_restart_attempts == 3
        assert config.max_concurrent_per_user == 5
        assert config.max_concurrent_global == 100
        assert config.default_tool_call_timeout == 30
        assert config.default_connect_timeout == 10

    def test_custom_config(self) -> None:
        """测试自定义配置"""
        config = ManagerConfig(
            scan_paths=["/custom/path"],
            state_directory="/tmp/state",
            command_allowlist=["uv", "python3"],
            tools_cache_ttl=300,
            idle_session_ttl=1200,
        )
        assert config.scan_paths == ["/custom/path"]
        assert config.state_directory == "/tmp/state"
        assert config.command_allowlist == ["uv", "python3"]
        assert config.tools_cache_ttl == 300
        assert config.idle_session_ttl == 1200

    def test_default_command_allowlist(self) -> None:
        """测试默认命令白名单"""
        config = ManagerConfig()
        assert "uv" in config.command_allowlist
        assert "python3" in config.command_allowlist
        assert "node" in config.command_allowlist
        assert "npx" in config.command_allowlist

    def test_admin_sources(self) -> None:
        """测试 admin_sources 配置"""
        config = ManagerConfig(
            admin_sources=[
                AdminSource(
                    id="rag_mcp",
                    name="RAG MCP",
                    transport="sse",
                    sse={"url": "http://127.0.0.1:12311/sse"},
                ),
            ],
        )
        assert len(config.admin_sources) == 1
        assert config.admin_sources[0].id == "rag_mcp"


class TestLoadConfig:
    """load_config 函数测试"""

    def test_load_from_explicit_path(self, tmp_path: Path) -> None:
        """测试从显式路径加载"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "scan_paths": ["/test/path"],
                    "tools_cache_ttl": 300,
                },
            ),
        )

        config = load_config(str(config_file))
        assert config.scan_paths == ["/test/path"]
        assert config.tools_cache_ttl == 300

    def test_load_from_env_variable(self, tmp_path: Path) -> None:
        """测试从环境变量路径加载"""
        config_file = tmp_path / "env_config.yaml"
        config_file.write_text(
            yaml.dump({"idle_session_ttl": 900}),
        )

        with patch.dict("os.environ", {"WITTY_MCP_CONFIG": str(config_file)}):
            config = load_config()
            assert config.idle_session_ttl == 900

    def test_load_default_when_no_file(self) -> None:
        """测试无配置文件时使用默认值"""
        with patch.dict("os.environ", {}, clear=True):
            config = load_config("/nonexistent/path.yaml")
            assert isinstance(config, ManagerConfig)
            # 应使用默认值
            assert config.tools_cache_ttl == 600

    def test_load_empty_yaml(self, tmp_path: Path) -> None:
        """测试空 YAML 文件"""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        config = load_config(str(config_file))
        assert isinstance(config, ManagerConfig)
        # 空文件应回退到默认值
        assert config.tools_cache_ttl == 600

    def test_load_invalid_yaml_fallback(self, tmp_path: Path) -> None:
        """测试无效 YAML 时回退到默认值"""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("scan_paths: [not_a_list\n  broken: yaml: content")

        # 应该回退到默认配置，不崩溃
        config = load_config(str(config_file))
        assert isinstance(config, ManagerConfig)

    def test_load_none_path(self) -> None:
        """测试 None 路径"""
        with patch.dict("os.environ", {}, clear=True):
            config = load_config(None)
            assert isinstance(config, ManagerConfig)


class TestGetConfigAndReset:
    """get_config / reset_config 测试"""

    def setup_method(self) -> None:
        """每个测试前重置全局配置"""
        reset_config()

    def teardown_method(self) -> None:
        """每个测试后重置全局配置"""
        reset_config()

    def test_get_config_returns_singleton(self) -> None:
        """测试 get_config 返回单例"""
        with patch.dict("os.environ", {}, clear=True):
            config1 = get_config()
            config2 = get_config()
            assert config1 is config2

    def test_reset_config_clears_singleton(self) -> None:
        """测试 reset_config 清除单例"""
        with patch.dict("os.environ", {}, clear=True):
            config1 = get_config()
            reset_config()
            config2 = get_config()
            assert config1 is not config2
