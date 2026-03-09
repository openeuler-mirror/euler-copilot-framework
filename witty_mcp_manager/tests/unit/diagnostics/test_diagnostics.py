"""Diagnostics 模块单元测试

测试用例：
- TC003: 命令 allowlist 检查（python3）
- TC004: 命令 allowlist 检查（bash）
- TC005: 依赖缺失探测
"""

from unittest.mock import patch

import pytest

from witty_mcp_manager.diagnostics.checker import Checker
from witty_mcp_manager.diagnostics.preflight import PreflightChecker
from witty_mcp_manager.registry.models import (
    NormalizedConfig,
    ServerRecord,
    SourceType,
    SseConfig,
    StdioConfig,
    TransportType,
)


class TestPreflightChecker:
    """PreflightChecker 测试"""

    @pytest.fixture
    def preflight(self, mock_config):
        return PreflightChecker(mock_config)

    @pytest.fixture
    def sample_server(self, tmp_path):
        """创建示例 ServerRecord"""
        return ServerRecord(
            id="test_mcp",
            name="Test MCP",
            source=SourceType.RPM,
            install_root=str(tmp_path / "test_mcp"),
            upstream_key="test_mcp",
            transport=TransportType.STDIO,
            default_config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="uv", args=["run", "server.py"]),
            ),
            rpm_metadata={
                "dependencies": {
                    "system": ["python3", "uv"],
                    "packages": ["git", "jq"],
                },
            },
        )

    def test_command_allowed_python3(self, preflight):
        """TC003: python3 在白名单中"""
        assert preflight.check_command_allowlist("python3") is True

    def test_command_allowed_uv(self, preflight):
        """uv 在白名单中"""
        assert preflight.check_command_allowlist("uv") is True

    def test_command_allowed_node(self, preflight):
        """node 在白名单中"""
        assert preflight.check_command_allowlist("node") is True

    def test_command_not_allowed_bash(self, preflight):
        """TC004: bash 不在白名单中"""
        assert preflight.check_command_allowlist("bash") is False

    def test_command_not_allowed_rm(self, preflight):
        """rm 不在白名单中"""
        assert preflight.check_command_allowlist("rm") is False

    def test_command_not_allowed_curl(self, preflight):
        """curl 不在白名单中"""
        assert preflight.check_command_allowlist("curl") is False

    @patch("shutil.which")
    def test_command_exists(self, mock_which, preflight):
        """命令存在性检查"""
        mock_which.return_value = "/usr/bin/python3"
        assert preflight.check_command_exists("python3") is True

        mock_which.return_value = None
        assert preflight.check_command_exists("nonexistent") is False

    @patch("shutil.which")
    def test_check_dependencies_all_present(self, mock_which, preflight, sample_server):
        """TC005: 所有依赖都存在"""
        # 所有命令都存在
        mock_which.return_value = "/usr/bin/command"

        missing = preflight.check_dependencies(sample_server)

        assert missing["system"] == []
        assert missing["packages"] == []

    @patch("shutil.which")
    def test_check_dependencies_missing(self, mock_which, preflight, sample_server):
        """TC005: 依赖缺失检测"""

        # 模拟 jq 不存在
        def which_side_effect(cmd):
            if cmd == "jq":
                return None
            return f"/usr/bin/{cmd}"

        mock_which.side_effect = which_side_effect

        missing = preflight.check_dependencies(sample_server)

        assert "jq" in missing["packages"]

    def test_generate_suggestions(self, preflight):
        """生成修复建议"""
        missing = {
            "system": ["python3"],
            "packages": ["git", "jq"],
            "python": [],
        }

        suggestions = preflight.generate_suggestions(missing)

        assert len(suggestions) >= 2
        assert any("dnf install python3" in s for s in suggestions)
        assert any("dnf install git jq" in s for s in suggestions)

    @patch("shutil.which")
    def test_run_preflight_command_not_allowed(self, mock_which, preflight, sample_server):
        """预检查：命令不在白名单"""
        # 修改命令为不允许的
        sample_server.default_config.stdio.command = "bash"
        mock_which.return_value = "/bin/bash"

        diagnostics = preflight.run_preflight(sample_server)

        assert diagnostics.command_allowed is False
        assert any("not in allowlist" in e for e in diagnostics.errors)

    @patch("shutil.which")
    def test_run_preflight_command_not_found(self, mock_which, preflight, sample_server):
        """预检查：命令不存在"""
        mock_which.return_value = None

        diagnostics = preflight.run_preflight(sample_server)

        assert diagnostics.command_exists is False
        assert any("not found" in w for w in diagnostics.warnings)


class TestChecker:
    """Checker 测试"""

    @pytest.fixture
    def checker(self):
        return Checker()

    @pytest.fixture
    def server_with_files(self, tmp_path):
        """创建带有完整文件的 server"""
        server_dir = tmp_path / "test_mcp"
        server_dir.mkdir()
        (server_dir / "mcp_config.json").write_text("{}")
        (server_dir / "src").mkdir()
        (server_dir / "src" / "server.py").write_text("")

        return ServerRecord(
            id="test_mcp",
            name="Test MCP",
            source=SourceType.RPM,
            install_root=str(server_dir),
            upstream_key="test_mcp",
            transport=TransportType.STDIO,
            default_config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="uv", args=[]),
            ),
        )

    def test_check_files_all_present(self, checker, server_with_files):
        """所有必要文件存在"""
        missing = checker.check_files(server_with_files)
        assert missing == []

    def test_check_files_missing_config(self, checker, tmp_path):
        """缺少 mcp_config.json 和 config.json"""
        server_dir = tmp_path / "no_config"
        server_dir.mkdir()
        (server_dir / "src").mkdir()

        server = ServerRecord(
            id="no_config",
            name="No Config",
            source=SourceType.RPM,
            install_root=str(server_dir),
            upstream_key="no_config",
            transport=TransportType.STDIO,
            default_config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="uv", args=[]),
            ),
        )

        missing = checker.check_files(server)
        assert "mcp_config.json or config.json" in missing

    def test_check_files_missing_src(self, checker, tmp_path):
        """缺少 src 目录"""
        server_dir = tmp_path / "no_src"
        server_dir.mkdir()
        (server_dir / "mcp_config.json").write_text("{}")

        server = ServerRecord(
            id="no_src",
            name="No Src",
            source=SourceType.RPM,
            install_root=str(server_dir),
            upstream_key="no_src",
            transport=TransportType.STDIO,
            default_config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="uv", args=[]),
            ),
        )

        missing = checker.check_files(server)
        assert "src/" in missing

    def test_check_config_validity_stdio_missing_command(self, checker):
        """STDIO 配置缺少 command - Pydantic 验证阶段即失败"""
        from pydantic import ValidationError

        # Pydantic v2 的严格验证在模型构建阶段就会拒绝空 command
        # 空字符串触发 min_length=1 约束
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            StdioConfig(command="", args=[])

        # 使用 whitespace-only command 触发 field_validator
        with pytest.raises(ValidationError, match="command cannot be empty"):
            StdioConfig(command="   ", args=[])

    def test_check_config_validity_transport_mismatch(self, checker):
        """传输类型与配置不匹配 - Pydantic 验证阶段即失败"""
        from pydantic import ValidationError

        # Pydantic v2 的 model_validator 在构建阶段就会检查一致性
        with pytest.raises(ValidationError, match="STDIO transport requires stdio config"):
            NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=None,  # STDIO 传输但没有 stdio 配置
            )

    def test_validate_full(self, checker, server_with_files):
        """完整校验"""
        diagnostics = checker.validate(server_with_files)

        assert diagnostics.config_valid is True
        assert diagnostics.is_ready is True

    def test_check_files_config_json_accepted(self, checker, tmp_path):
        """config.json 也被接受为有效配置文件（mcp_center 格式）"""
        server_dir = tmp_path / "sse_mcp"
        server_dir.mkdir()
        (server_dir / "config.json").write_text("{}")

        server = ServerRecord(
            id="sse_mcp",
            name="SSE MCP",
            source=SourceType.ADMIN,
            install_root=str(server_dir),
            upstream_key="sse_mcp",
            transport=TransportType.SSE,
            default_config=NormalizedConfig(
                transport=TransportType.SSE,
                sse=SseConfig(url="http://127.0.0.1:8080/sse"),
            ),
        )

        missing = checker.check_files(server)
        # config.json 存在；src/ 缺失会被报告，但 validate 中仅作为 warning
        assert "mcp_config.json or config.json" not in missing
        assert "src/" in missing

    def test_missing_src_is_warning_not_error(self, checker, tmp_path):
        """缺少 src/ 时 validate 产生 warning 而非 error，不影响 config_valid"""
        server_dir = tmp_path / "no_src_server"
        server_dir.mkdir()
        (server_dir / "mcp_config.json").write_text("{}")
        # 故意不创建 src/ 目录

        server = ServerRecord(
            id="no_src_server",
            name="No Src Server",
            source=SourceType.RPM,
            install_root=str(server_dir),
            upstream_key="no_src_server",
            transport=TransportType.STDIO,
            default_config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="uv", args=[]),
            ),
        )

        # check_files 会报告 src/ 缺失
        missing = checker.check_files(server)
        assert "src/" in missing

        # 但 validate 将其降级为 warning，config_valid 不受影响
        diagnostics = checker.validate(server)
        assert diagnostics.config_valid is True
        assert diagnostics.is_ready is True
        assert any("src/" in w for w in diagnostics.warnings)

    def test_validate_sse_server_with_config_json(self, checker, tmp_path):
        """完整校验：SSE 服务器使用 config.json（mcp_center 格式）"""
        server_dir = tmp_path / "mcp_server_mcp"
        server_dir.mkdir()
        (server_dir / "config.json").write_text("{}")

        server = ServerRecord(
            id="mcp_server_mcp",
            name="oe-智能运维工具",
            source=SourceType.ADMIN,
            install_root=str(server_dir),
            upstream_key="mcp_server_mcp",
            transport=TransportType.SSE,
            default_config=NormalizedConfig(
                transport=TransportType.SSE,
                sse=SseConfig(url="http://127.0.0.1:12555/sse"),
            ),
        )

        diagnostics = checker.validate(server)
        assert diagnostics.config_valid is True
        assert diagnostics.is_ready is True
        # src/ 缺失仅为 warning
        assert any("src/" in w for w in diagnostics.warnings)
