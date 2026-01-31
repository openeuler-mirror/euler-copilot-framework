"""
Overlay 模块单元测试
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from witty_mcp_manager.overlay.resolver import EffectiveConfig, OverlayResolver
from witty_mcp_manager.overlay.storage import OverlayStorage
from witty_mcp_manager.registry.models import (
    Concurrency,
    NormalizedConfig,
    Override,
    ServerRecord,
    SourceType,
    StdioConfig,
    Timeouts,
    TransportType,
)


class TestOverlayStorage:
    """OverlayStorage 测试"""

    @pytest.fixture
    def temp_state_dir(self) -> Path:
        """创建临时 state 目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def storage(self, temp_state_dir: Path) -> OverlayStorage:
        """创建存储实例"""
        storage = OverlayStorage(temp_state_dir)
        storage.ensure_directories()
        return storage

    def test_ensure_directories(self, temp_state_dir: Path) -> None:
        """测试目录创建"""
        storage = OverlayStorage(temp_state_dir)
        storage.ensure_directories()

        assert storage.global_dir.exists()
        assert storage.users_dir.exists()

    def test_save_and_load_global_override(self, storage: OverlayStorage) -> None:
        """测试保存和加载全局覆盖配置"""
        override = Override(
            scope="global",
            disabled=True,
            env={"DEBUG": "1"},
        )

        # 保存
        path = storage.save_override("git_mcp", override)
        assert path.exists()

        # 加载
        loaded = storage.load_override("git_mcp")
        assert loaded is not None
        assert loaded.disabled is True
        assert loaded.env == {"DEBUG": "1"}

    def test_save_and_load_user_override(self, storage: OverlayStorage) -> None:
        """测试保存和加载用户覆盖配置"""
        override = Override(
            scope="user/user123",
            disabled=False,
            env={"USER_ENV": "test"},
        )

        # 保存
        path = storage.save_override("git_mcp", override, user_id="user123")
        assert path.exists()
        assert "users/user123" in str(path)

        # 加载
        loaded = storage.load_override("git_mcp", user_id="user123")
        assert loaded is not None
        assert loaded.disabled is False
        assert loaded.env == {"USER_ENV": "test"}

    def test_load_nonexistent_override(self, storage: OverlayStorage) -> None:
        """测试加载不存在的覆盖配置"""
        loaded = storage.load_override("nonexistent_mcp")
        assert loaded is None

    def test_delete_override(self, storage: OverlayStorage) -> None:
        """测试删除覆盖配置"""
        override = Override(scope="global", disabled=True)
        storage.save_override("git_mcp", override)

        # 删除
        assert storage.delete_override("git_mcp") is True
        assert storage.load_override("git_mcp") is None

        # 重复删除
        assert storage.delete_override("git_mcp") is False

    def test_list_global_overrides(self, storage: OverlayStorage) -> None:
        """测试列出全局覆盖配置"""
        storage.save_override("mcp1", Override(scope="global"))
        storage.save_override("mcp2", Override(scope="global"))

        overrides = storage.list_global_overrides()
        assert set(overrides) == {"mcp1", "mcp2"}

    def test_list_user_overrides(self, storage: OverlayStorage) -> None:
        """测试列出用户覆盖配置"""
        storage.save_override("mcp1", Override(scope="user/user1"), user_id="user1")
        storage.save_override("mcp2", Override(scope="user/user1"), user_id="user1")

        overrides = storage.list_user_overrides("user1")
        assert set(overrides) == {"mcp1", "mcp2"}

    def test_list_all_users(self, storage: OverlayStorage) -> None:
        """测试列出所有用户"""
        storage.save_override("mcp1", Override(scope="user/user1"), user_id="user1")
        storage.save_override("mcp2", Override(scope="user/user2"), user_id="user2")

        users = storage.list_all_users()
        assert set(users) == {"user1", "user2"}

    def test_is_globally_disabled(self, storage: OverlayStorage) -> None:
        """测试检查全局禁用状态"""
        # 未配置
        assert storage.is_globally_disabled("mcp1") is False

        # 禁用
        storage.save_override("mcp1", Override(scope="global", disabled=True))
        assert storage.is_globally_disabled("mcp1") is True

        # 启用
        storage.save_override("mcp2", Override(scope="global", disabled=False))
        assert storage.is_globally_disabled("mcp2") is False

    def test_is_user_enabled(self, storage: OverlayStorage) -> None:
        """测试检查用户启用状态"""
        # 未配置
        assert storage.is_user_enabled("mcp1", "user1") is None

        # 启用
        storage.save_override("mcp1", Override(scope="user/user1", disabled=False), user_id="user1")
        assert storage.is_user_enabled("mcp1", "user1") is True

        # 禁用
        storage.save_override("mcp2", Override(scope="user/user1", disabled=True), user_id="user1")
        assert storage.is_user_enabled("mcp2", "user1") is False


class TestOverlayResolver:
    """OverlayResolver 测试"""

    @pytest.fixture
    def temp_state_dir(self) -> Path:
        """创建临时 state 目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def storage(self, temp_state_dir: Path) -> OverlayStorage:
        """创建存储实例"""
        storage = OverlayStorage(temp_state_dir)
        storage.ensure_directories()
        return storage

    @pytest.fixture
    def resolver(self, storage: OverlayStorage) -> OverlayResolver:
        """创建解析器实例"""
        return OverlayResolver(storage)

    @pytest.fixture
    def sample_server(self) -> ServerRecord:
        """创建示例 ServerRecord"""
        return ServerRecord(
            id="git_mcp",
            name="Git MCP Server",
            summary="Git 仓库管理",
            source=SourceType.RPM,
            install_root="/opt/mcp-servers/servers/git_mcp",
            upstream_key="git_mcp",
            transport=TransportType.STDIO,
            default_disabled=False,
            default_config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(
                    command="uv",
                    args=["--directory", "/opt/mcp-servers/servers/git_mcp/src", "run", "server.py"],
                    env={"DEFAULT_ENV": "value"},
                ),
                timeouts=Timeouts(tool_call=30, idle_ttl=600),
            ),
        )

    def test_resolve_default_config(
        self,
        resolver: OverlayResolver,
        sample_server: ServerRecord,
    ) -> None:
        """测试解析默认配置（无覆盖）"""
        effective = resolver.resolve(sample_server)

        assert effective.mcp_id == "git_mcp"
        assert effective.disabled is False
        assert effective.env == {"DEFAULT_ENV": "value"}
        assert effective.timeouts.tool_call == 30

    def test_resolve_with_global_override(
        self,
        resolver: OverlayResolver,
        storage: OverlayStorage,
        sample_server: ServerRecord,
    ) -> None:
        """测试解析全局覆盖配置"""
        # 保存全局覆盖
        storage.save_override(
            "git_mcp",
            Override(
                scope="global",
                env={"GLOBAL_ENV": "global_value"},
                timeouts=Timeouts(tool_call=60),
            ),
        )

        effective = resolver.resolve(sample_server)

        # env 合并
        assert effective.env["DEFAULT_ENV"] == "value"
        assert effective.env["GLOBAL_ENV"] == "global_value"
        # timeouts 覆盖
        assert effective.timeouts.tool_call == 60

    def test_resolve_with_user_override(
        self,
        resolver: OverlayResolver,
        storage: OverlayStorage,
        sample_server: ServerRecord,
    ) -> None:
        """测试解析用户覆盖配置"""
        # 保存全局覆盖
        storage.save_override(
            "git_mcp",
            Override(scope="global", env={"GLOBAL_ENV": "global"}),
        )
        # 保存用户覆盖
        storage.save_override(
            "git_mcp",
            Override(scope="user/user123", env={"USER_ENV": "user"}),
            user_id="user123",
        )

        effective = resolver.resolve(sample_server, user_id="user123")

        # 三层 env 合并
        assert effective.env["DEFAULT_ENV"] == "value"
        assert effective.env["GLOBAL_ENV"] == "global"
        assert effective.env["USER_ENV"] == "user"

    def test_resolve_disabled_priority(
        self,
        resolver: OverlayResolver,
        storage: OverlayStorage,
        sample_server: ServerRecord,
    ) -> None:
        """测试禁用状态优先级：用户 > 全局 > 默认"""
        # 全局禁用
        storage.save_override(
            "git_mcp",
            Override(scope="global", disabled=True),
        )

        # 仅全局配置
        effective = resolver.resolve(sample_server)
        assert effective.disabled is True

        # 用户覆盖启用
        storage.save_override(
            "git_mcp",
            Override(scope="user/user123", disabled=False),
            user_id="user123",
        )

        effective = resolver.resolve(sample_server, user_id="user123")
        assert effective.disabled is False

    def test_is_enabled_for_user(
        self,
        resolver: OverlayResolver,
        storage: OverlayStorage,
        sample_server: ServerRecord,
    ) -> None:
        """测试用户启用检查"""
        # 默认启用
        assert resolver.is_enabled_for_user(sample_server, "user1") is True

        # 全局禁用
        storage.save_override("git_mcp", Override(scope="global", disabled=True))
        assert resolver.is_enabled_for_user(sample_server, "user1") is False

        # 用户覆盖启用
        storage.save_override(
            "git_mcp",
            Override(scope="user/user1", disabled=False),
            user_id="user1",
        )
        assert resolver.is_enabled_for_user(sample_server, "user1") is True

    def test_arg_patches_add(
        self,
        resolver: OverlayResolver,
        storage: OverlayStorage,
        sample_server: ServerRecord,
    ) -> None:
        """测试参数补丁：添加"""
        storage.save_override(
            "git_mcp",
            Override(
                scope="global",
                arg_patches=[{"op": "add", "value": "--verbose"}],
            ),
        )

        effective = resolver.resolve(sample_server)
        assert "--verbose" in effective.config.stdio.args

    def test_arg_patches_remove(
        self,
        resolver: OverlayResolver,
        storage: OverlayStorage,
        sample_server: ServerRecord,
    ) -> None:
        """测试参数补丁：移除"""
        storage.save_override(
            "git_mcp",
            Override(
                scope="global",
                arg_patches=[{"op": "remove", "value": "server.py"}],
            ),
        )

        effective = resolver.resolve(sample_server)
        assert "server.py" not in effective.config.stdio.args

    def test_get_enabled_servers(
        self,
        resolver: OverlayResolver,
        storage: OverlayStorage,
        sample_server: ServerRecord,
    ) -> None:
        """测试获取启用的 server 列表"""
        server2 = ServerRecord(
            id="rpm_builder",
            name="RPM Builder",
            source=SourceType.RPM,
            install_root="/opt/mcp-servers/servers/rpm_builder",
            upstream_key="rpm_builder",
            transport=TransportType.STDIO,
            default_disabled=False,
            default_config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="uv", args=[]),
            ),
        )

        servers = [sample_server, server2]

        # 全部启用
        enabled = resolver.get_enabled_servers(servers)
        assert len(enabled) == 2

        # 禁用一个
        storage.save_override("git_mcp", Override(scope="global", disabled=True))
        enabled = resolver.get_enabled_servers(servers)
        assert len(enabled) == 1
        assert enabled[0].id == "rpm_builder"
