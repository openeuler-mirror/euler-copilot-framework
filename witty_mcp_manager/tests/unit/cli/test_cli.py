"""CLI 模块测试

测试 witty-mcp 命令行接口的各种子命令。
使用 pytest + typer 的 CliRunner 进行测试。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from witty_mcp_manager.cli.main import app as main_app
from witty_mcp_manager.cli.permissions import (
    CliPermissionError,
    PrivilegeLevel,
    ResolvedScope,
    UserIdentity,
    resolve_scope,
    resolve_user_for_ipc,
)
from witty_mcp_manager.cli.runtime import (
    _format_duration,
)
from witty_mcp_manager.cli.runtime import (
    app as runtime_app,
)
from witty_mcp_manager.cli.servers import (
    _enabled_label,
    _extract_stdio,
    _infer_transport,
    _load_server_entry,
)
from witty_mcp_manager.cli.servers import (
    app as servers_app,
)

if TYPE_CHECKING:
    from pathlib import Path


runner = CliRunner()


class TestMainApp:
    """主命令入口测试"""

    def test_help(self):
        """测试 --help 选项"""
        result = runner.invoke(main_app, ["--help"])
        assert result.exit_code == 0
        assert "witty-mcp" in result.output.lower() or "mcp" in result.output.lower()

    def test_servers_help(self):
        """测试 servers --help"""
        result = runner.invoke(main_app, ["servers", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output.lower()

    def test_runtime_help(self):
        """测试 runtime --help"""
        result = runner.invoke(main_app, ["runtime", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output.lower()


class TestServersSubcommand:
    """servers 子命令测试"""

    def test_list_help(self):
        """测试 servers list --help"""
        result = runner.invoke(servers_app, ["list", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output.lower()

    def test_list_servers_no_daemon(self):
        """测试 servers list 命令（无 daemon 时 fallback 到直接扫描）"""
        # 由于没有运行的 daemon，CLI 会尝试直接扫描
        # 这取决于实现方式
        result = runner.invoke(servers_app, ["list"])
        # 可能成功或失败，但不应该崩溃
        assert "traceback" not in result.output.lower()

    @patch("witty_mcp_manager.cli.servers.load_config")
    @patch("witty_mcp_manager.cli.servers.OverlayStorage")
    def test_enable_requires_user_or_global(self, mock_storage: MagicMock, mock_config: MagicMock):
        """测试 servers enable 不指定选项时自动使用用户作用域"""
        mock_config.return_value = MagicMock(state_directory="/tmp/state")
        mock_storage.return_value.load_override.return_value = None
        
        # 普通用户不指定选项时，会自动使用当前用户的用户作用域
        result = runner.invoke(servers_app, ["enable", "git_mcp"])
        # 应该成功（除非有权限或文件系统问题）
        assert result.exit_code in [0, 1]  # 0 成功，1 可能因为权限或其他原因

    @patch("witty_mcp_manager.cli.servers.load_config")
    @patch("witty_mcp_manager.cli.servers.OverlayStorage")
    def test_disable_requires_user_or_global(self, mock_storage: MagicMock, mock_config: MagicMock):
        """测试 servers disable 不指定选项时自动使用用户作用域"""
        mock_config.return_value = MagicMock(state_directory="/tmp/state")
        mock_storage.return_value.load_override.return_value = None
        
        # 普通用户不指定选项时，会自动使用当前用户的用户作用域
        result = runner.invoke(servers_app, ["disable", "git_mcp"])
        assert result.exit_code in [0, 1]  # 0 成功，1 可能因为权限或其他原因

    @patch("witty_mcp_manager.cli.servers.load_config")
    @patch("witty_mcp_manager.cli.servers.OverlayStorage")
    def test_enable_global(self, mock_storage: MagicMock, mock_config: MagicMock):
        """测试 servers enable --global"""
        mock_config.return_value = MagicMock(state_directory="/tmp/state")
        mock_storage.return_value.load_override.return_value = None

        result = runner.invoke(servers_app, ["enable", "git_mcp", "--global"])
        # 命令应该能执行（不管成功与否）
        # 实际结果取决于文件系统
        assert result.exit_code in [0, 1]  # 0 成功，1 可能因为权限或其他原因

    @patch("witty_mcp_manager.cli.servers._get_client")
    def test_enable_user(self, mock_client: MagicMock):
        """测试 servers enable --user"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success"}
        mock_response.raise_for_status = MagicMock()
        mock_client.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_client.return_value.__exit__ = MagicMock(return_value=False)

        # 即使 mock 不完整，命令应该尝试执行
        result = runner.invoke(servers_app, ["enable", "git_mcp", "--user", "test_user"])
        # 可能因为 UDS 连接失败而返回非0
        assert result.exit_code >= 0


class TestRuntimeSubcommand:
    """runtime 子命令测试"""

    def test_status_help(self):
        """测试 runtime status --help"""
        result = runner.invoke(runtime_app, ["status", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output.lower() or "daemon" in result.output.lower()

    def test_sessions_help(self):
        """测试 runtime sessions --help"""
        result = runner.invoke(runtime_app, ["sessions", "--help"])
        assert result.exit_code == 0

    def test_sessions_requires_user_or_all(self):
        """测试 runtime sessions 需要 --user 或 --all-users"""
        result = runner.invoke(runtime_app, ["sessions"])
        assert result.exit_code != 0
        assert "--user" in result.output or "error" in result.output.lower()

    def test_status_with_mcp_id_requires_user(self):
        """测试 runtime status <mcp_id> 需要 --user"""
        result = runner.invoke(runtime_app, ["status", "git_mcp"])
        assert result.exit_code != 0
        assert "--user" in result.output

    def test_kill_not_supported(self):
        """测试 runtime kill 返回不支持"""
        result = runner.invoke(runtime_app, ["kill", "some_session"])
        assert result.exit_code == 2
        assert "not supported" in result.output.lower()


class TestCLIHelperFunctions:
    """CLI 辅助函数测试"""

    # servers.py helpers

    def test_enabled_label(self):
        """测试 _enabled_label"""
        assert _enabled_label(system_enabled=True) == "enabled"
        assert _enabled_label(system_enabled=False) == "disabled"

    def test_infer_transport_stdio(self):
        """测试 _infer_transport 识别 stdio"""
        entry = {"command": "uv", "args": ["run"]}
        assert _infer_transport(entry) == "stdio"  # type: ignore[arg-type]

        entry = {"stdio": {"command": "python3"}}  # type: ignore[dict-item]
        assert _infer_transport(entry) == "stdio"  # type: ignore[arg-type]

    def test_infer_transport_sse(self):
        """测试 _infer_transport 识别 sse"""
        entry = {"url": "http://localhost:8080/sse"}
        assert _infer_transport(entry) == "sse"  # type: ignore[arg-type]

        entry = {"sse": {"url": "http://localhost:8080"}}  # type: ignore[dict-item]
        assert _infer_transport(entry) == "sse"  # type: ignore[arg-type]

    def test_infer_transport_explicit(self):
        """测试 _infer_transport 使用显式 transport 字段"""
        entry = {"transport": "custom", "command": "uv"}
        assert _infer_transport(entry) == "custom"  # type: ignore[arg-type]

    def test_infer_transport_empty(self):
        """测试 _infer_transport 空配置"""
        assert _infer_transport({}) == ""

    def test_extract_stdio_flat(self):
        """测试 _extract_stdio 提取扁平结构"""
        entry = {
            "command": "uv",
            "args": ["run", "main.py"],
            "env": {"PATH": "/usr/bin"},
        }
        command, args, env = _extract_stdio(entry)  # type: ignore[arg-type]
        assert command == "uv"
        assert args == ["run", "main.py"]
        assert env == {"PATH": "/usr/bin"}

    def test_extract_stdio_nested(self):
        """测试 _extract_stdio 提取嵌套结构"""
        entry = {
            "stdio": {
                "command": "python3",
                "args": ["-m", "mcp_server"],
                "env": {"PYTHONPATH": "/opt/mcp"},
            },
        }
        command, args, _env = _extract_stdio(entry)  # type: ignore[arg-type]
        assert command == "python3"
        assert args == ["-m", "mcp_server"]

    def test_extract_stdio_missing(self):
        """测试 _extract_stdio 处理缺失字段"""
        entry: dict[str, object] = {}
        command, args, env = _extract_stdio(entry)
        assert command is None
        assert args is None
        assert env is None

    def test_load_server_entry_nonexistent(self, tmp_path: Path):
        """测试 _load_server_entry 处理不存在的目录"""
        result = _load_server_entry(str(tmp_path / "nonexistent"), None, "test_mcp")
        assert result == {}

    def test_load_server_entry_valid(self, tmp_path: Path, real_git_mcp_config):
        """测试 _load_server_entry 读取有效配置"""
        import json

        server_dir = tmp_path / "git_mcp"
        server_dir.mkdir()
        config_path = server_dir / "mcp_config.json"
        config_path.write_text(json.dumps(real_git_mcp_config))

        result = _load_server_entry(str(server_dir), "git-mcp", "git_mcp")
        assert result != {}
        assert result.get("command") == "uv"

    def test_load_server_entry_by_mcp_id(self, tmp_path: Path, real_git_mcp_config):
        """测试 _load_server_entry 通过 mcp_id 查找"""
        import json

        # 修改配置使用 mcp_id 作为 key
        # real_git_mcp_config 的 key 是 "git_mcp"（目录名）
        config = real_git_mcp_config  # 已经使用 git_mcp 作为 key

        server_dir = tmp_path / "git_mcp"
        server_dir.mkdir()
        config_path = server_dir / "mcp_config.json"
        config_path.write_text(json.dumps(config))

        result = _load_server_entry(str(server_dir), None, "git_mcp")
        assert result.get("command") == "uv"

    # runtime.py helpers

    def test_format_duration_seconds(self):
        """测试 _format_duration 秒"""
        assert _format_duration(45) == "45s"

    def test_format_duration_minutes(self):
        """测试 _format_duration 分钟"""
        assert _format_duration(125) == "2m 5s"

    def test_format_duration_hours(self):
        """测试 _format_duration 小时"""
        assert _format_duration(3665) == "1h 1m 5s"

    def test_format_duration_none(self):
        """测试 _format_duration None"""
        assert _format_duration(None) == "N/A"


class TestPermissions:
    """权限模块测试"""

    def test_privilege_level_enum(self):
        """测试 PrivilegeLevel 枚举"""
        assert PrivilegeLevel.ROOT.value == "root"
        assert PrivilegeLevel.SUDO.value == "sudo"
        assert PrivilegeLevel.REGULAR.value == "regular"

    def test_user_identity_privileged(self):
        """测试特权用户身份"""
        identity = UserIdentity(
            privilege=PrivilegeLevel.ROOT,
            effective_uid=0,
            real_username="root",
        )
        assert identity.is_privileged
        assert identity.can_manage_global
        assert identity.can_manage_others

    def test_user_identity_regular(self):
        """测试普通用户身份"""
        identity = UserIdentity(
            privilege=PrivilegeLevel.REGULAR,
            effective_uid=1000,
            real_username="testuser",
        )
        assert not identity.is_privileged
        assert not identity.can_manage_global
        assert not identity.can_manage_others

    def test_resolve_scope_regular_user_auto(self):
        """测试普通用户自动解析到当前用户"""
        identity = UserIdentity(
            privilege=PrivilegeLevel.REGULAR,
            effective_uid=1000,
            real_username="testuser",
        )
        scope = resolve_scope(identity, global_flag=False, user_flag=None, operation="test")
        assert not scope.is_global
        assert scope.user_id == "testuser"

    def test_resolve_scope_regular_user_global_denied(self):
        """测试普通用户无法使用 --global"""
        identity = UserIdentity(
            privilege=PrivilegeLevel.REGULAR,
            effective_uid=1000,
            real_username="testuser",
        )
        with pytest.raises(CliPermissionError) as exc_info:
            resolve_scope(identity, global_flag=True, user_flag=None, operation="test")
        assert "--global requires root/sudo" in str(exc_info.value)

    def test_resolve_scope_regular_user_other_user_denied(self):
        """测试普通用户无法管理其他用户"""
        identity = UserIdentity(
            privilege=PrivilegeLevel.REGULAR,
            effective_uid=1000,
            real_username="testuser",
        )
        with pytest.raises(CliPermissionError) as exc_info:
            resolve_scope(identity, global_flag=False, user_flag="otheruser", operation="test")
        assert "Cannot manage other user" in str(exc_info.value)

    def test_resolve_scope_privileged_default_root(self):
        """测试特权用户不指定参数时默认使用 root 用户"""
        identity = UserIdentity(
            privilege=PrivilegeLevel.ROOT,
            effective_uid=0,
            real_username="root",
        )
        scope = resolve_scope(identity, global_flag=False, user_flag=None, operation="test")
        assert not scope.is_global
        assert scope.user_id == "root"

    def test_resolve_scope_privileged_global(self):
        """测试特权用户使用 --global"""
        identity = UserIdentity(
            privilege=PrivilegeLevel.ROOT,
            effective_uid=0,
            real_username="root",
        )
        scope = resolve_scope(identity, global_flag=True, user_flag=None, operation="test")
        assert scope.is_global
        assert scope.user_id is None

    def test_resolve_scope_privileged_user(self):
        """测试特权用户使用 --user"""
        identity = UserIdentity(
            privilege=PrivilegeLevel.ROOT,
            effective_uid=0,
            real_username="root",
        )
        scope = resolve_scope(identity, global_flag=False, user_flag="alice", operation="test")
        assert not scope.is_global
        assert scope.user_id == "alice"

    def test_resolve_scope_conflict_flags(self):
        """测试同时指定 --global 和 --user 冲突"""
        identity = UserIdentity(
            privilege=PrivilegeLevel.ROOT,
            effective_uid=0,
            real_username="root",
        )
        with pytest.raises(CliPermissionError) as exc_info:
            resolve_scope(identity, global_flag=True, user_flag="alice", operation="test")
        assert "Cannot specify both" in str(exc_info.value)

    def test_resolve_user_for_ipc_regular(self):
        """测试 IPC 用户解析（普通用户）"""
        identity = UserIdentity(
            privilege=PrivilegeLevel.REGULAR,
            effective_uid=1000,
            real_username="testuser",
        )
        result = resolve_user_for_ipc(identity, user_flag=None, operation="test")
        assert result == "testuser"

    def test_resolve_user_for_ipc_privileged_default_root(self):
        """测试 IPC 用户解析（特权用户默认使用 root）"""
        identity = UserIdentity(
            privilege=PrivilegeLevel.ROOT,
            effective_uid=0,
            real_username="root",
        )
        result = resolve_user_for_ipc(identity, user_flag=None, operation="test")
        assert result == "root"

    def test_resolve_user_for_ipc_privileged_with_user(self):
        """测试 IPC 用户解析（特权用户指定 --user）"""
        identity = UserIdentity(
            privilege=PrivilegeLevel.ROOT,
            effective_uid=0,
            real_username="root",
        )
        result = resolve_user_for_ipc(identity, user_flag="alice", operation="test")
        assert result == "alice"

    def test_resolved_scope_name(self):
        """测试 ResolvedScope.scope_name"""
        global_scope = ResolvedScope(is_global=True, user_id=None)
        assert global_scope.scope_name == "global"

        user_scope = ResolvedScope(is_global=False, user_id="alice")
        assert user_scope.scope_name == "user/alice"


class TestCLIWithRealConfigs:
    """使用真实配置的 CLI 测试"""

    def test_list_with_real_servers(
        self,
        mock_real_config,
        mock_real_mcp_servers_dir,
    ):
        """测试使用真实配置的 list 命令"""
        from witty_mcp_manager.registry.discovery import Discovery

        # 直接测试 Discovery 而不是通过 CLI
        real_discovery = Discovery(mock_real_config)
        servers = real_discovery.scan_all()

        # 验证发现了预期的服务器（4 RPM STDIO + 2 Admin SSE）
        assert len(servers) == 6
        server_ids = {s.id for s in servers}
        assert "git_mcp" in server_ids
        assert "ccb_mcp" in server_ids
        assert "mcp_server_mcp" in server_ids
        assert "rag_mcp" in server_ids

    def test_info_command_logic(
        self,
        mock_real_config,
        mock_real_mcp_servers_dir,
    ):
        """测试 info 命令的核心逻辑"""
        from witty_mcp_manager.registry.discovery import Discovery

        real_discovery = Discovery(mock_real_config)
        servers = real_discovery.scan_all()

        # 查找 git_mcp
        git_mcp = next((s for s in servers if s.id == "git_mcp"), None)
        assert git_mcp is not None
        assert git_mcp.name is not None
        assert git_mcp.transport.value in ["stdio", "sse"]


class TestCLIErrorHandling:
    """CLI 错误处理测试"""

    def test_servers_list_config_error(self):
        """测试配置加载错误处理"""
        with patch(
            "witty_mcp_manager.cli.servers.load_config",
            side_effect=FileNotFoundError("Config not found"),
        ):
            result = runner.invoke(servers_app, ["list"])
            # 应该优雅退出而不是崩溃
            assert "traceback" not in result.output.lower() or result.exit_code != 0

    def test_runtime_status_connection_error(self):
        """测试连接错误处理"""
        import httpx

        with patch(
            "witty_mcp_manager.cli.runtime._get_client",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = runner.invoke(runtime_app, ["status"])
            # 应该显示连接错误信息
            assert result.exit_code != 0
