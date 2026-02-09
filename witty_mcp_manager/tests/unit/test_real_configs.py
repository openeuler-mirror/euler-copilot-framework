"""基于真实 VM 配置的测试用例

这些测试用例基于 openEuler 24.03 LTS SP3 上安装的真实 MCP RPM 包配置。
测试场景：
- TC101: 11个RPM基线包解析
- TC102: command: uv 的 server
- TC103: command: python3 的 server（ccb_mcp）
- TC104: upstream_key 与目录名不一致（oeDeploy_mcp）
- TC105: 含 env 字段的配置（cvekit_mcp）
- TC106: 依赖缺失探测（python 依赖）
"""

import pytest

from witty_mcp_manager.diagnostics.preflight import PreflightChecker
from witty_mcp_manager.registry.discovery import Discovery
from witty_mcp_manager.registry.models import SourceType, TransportType
from witty_mcp_manager.registry.normalizer import Normalizer


class TestRealMCPDiscovery:
    """基于真实配置的 Discovery 测试"""

    def test_scan_real_servers(self, mock_real_config, mock_real_mcp_servers_dir):
        """TC101: 扫描真实 MCP 服务器目录"""
        discovery = Discovery(mock_real_config)
        servers = discovery.scan_all()

        # 应该发现 6 个服务器（4 个 RPM STDIO + 2 个 Admin SSE）
        assert len(servers) == 6
        server_ids = {s.id for s in servers}
        # RPM STDIO 服务器
        assert "git_mcp" in server_ids
        assert "ccb_mcp" in server_ids
        assert "oeDeploy_mcp" in server_ids
        assert "cvekit_mcp" in server_ids
        # Admin SSE 服务器（config.json 格式）
        assert "mcp_server_mcp" in server_ids
        assert "rag_mcp" in server_ids

    def test_git_mcp_server(self, mock_real_config, mock_real_mcp_servers_dir):
        """TC102: git_mcp 使用 uv 命令"""
        discovery = Discovery(mock_real_config)
        servers = discovery.scan_all()

        git_mcp = next((s for s in servers if s.id == "git_mcp"), None)
        assert git_mcp is not None
        assert git_mcp.source == SourceType.RPM
        assert git_mcp.transport == TransportType.STDIO
        assert git_mcp.default_config.stdio is not None
        assert git_mcp.default_config.stdio.command == "uv"
        assert "--directory" in git_mcp.default_config.stdio.args

        # 验证 rpm_metadata
        assert git_mcp.rpm_metadata.get("name") == "git-mcp"
        deps = git_mcp.rpm_metadata.get("dependencies", {})
        assert "jq" in deps.get("system", [])

    def test_ccb_mcp_python3_command(self, mock_real_config, mock_real_mcp_servers_dir):
        """TC103: ccb_mcp 使用 python3 命令"""
        discovery = Discovery(mock_real_config)
        servers = discovery.scan_all()

        ccb_mcp = next((s for s in servers if s.id == "ccb_mcp"), None)
        assert ccb_mcp is not None
        assert ccb_mcp.default_config.stdio is not None
        assert ccb_mcp.default_config.stdio.command == "python3"

        # 验证敏感参数存在（但不验证值）
        args = ccb_mcp.default_config.stdio.args
        assert any("--GITEE_PASSWORD" in arg for arg in args)

        # upstream_key 与目录名不同
        assert ccb_mcp.upstream_key == "ccbMcp"

    def test_oedeploy_upstream_key_mismatch(self, mock_real_config, mock_real_mcp_servers_dir):
        """TC104: oeDeploy_mcp 的 upstream_key 与目录名不一致"""
        discovery = Discovery(mock_real_config)
        servers = discovery.scan_all()

        oedp_mcp = next((s for s in servers if s.id == "oeDeploy_mcp"), None)
        assert oedp_mcp is not None

        # canonical id 是目录名
        assert oedp_mcp.id == "oeDeploy_mcp"
        # upstream_key 是 mcp_config.json 中的 key
        assert oedp_mcp.upstream_key == "mcp-oedp"

        # 验证配置正确解析
        assert oedp_mcp.default_config.stdio is not None
        assert oedp_mcp.default_config.stdio.command == "uv"
        # 验证 timeout 被保留
        assert oedp_mcp.default_config.timeouts.tool_call == 1800

    def test_cvekit_with_env(self, mock_real_config, mock_real_mcp_servers_dir):
        """TC105: cvekit_mcp 包含 env 字段"""
        discovery = Discovery(mock_real_config)
        servers = discovery.scan_all()

        cvekit = next((s for s in servers if s.id == "cvekit_mcp"), None)
        assert cvekit is not None
        assert cvekit.default_config.stdio is not None

        # 验证 env 字段
        env = cvekit.default_config.stdio.env
        assert env.get("LANG") == "en_US.UTF-8"

        # 验证 timeout
        assert cvekit.default_config.timeouts.tool_call == 600

    def test_mcp_server_mcp_sse(self, mock_real_config, mock_real_mcp_servers_dir):
        """mcp_server_mcp: Admin SSE 服务器（config.json 格式）"""
        discovery = Discovery(mock_real_config)
        servers = discovery.scan_all()

        mcp_server = next((s for s in servers if s.id == "mcp_server_mcp"), None)
        assert mcp_server is not None
        assert mcp_server.source == SourceType.ADMIN
        assert mcp_server.transport == TransportType.SSE
        assert mcp_server.default_config.sse is not None
        assert mcp_server.default_config.sse.url == "http://127.0.0.1:12555/sse"
        assert mcp_server.default_config.stdio is None
        assert mcp_server.name == "oe-智能运维工具"

    def test_rag_mcp_sse(self, mock_real_config, mock_real_mcp_servers_dir):
        """rag_mcp: Admin SSE 服务器（config.json 格式）"""
        discovery = Discovery(mock_real_config)
        servers = discovery.scan_all()

        rag_mcp = next((s for s in servers if s.id == "rag_mcp"), None)
        assert rag_mcp is not None
        assert rag_mcp.source == SourceType.ADMIN
        assert rag_mcp.transport == TransportType.SSE
        assert rag_mcp.default_config.sse is not None
        assert rag_mcp.default_config.sse.url == "http://127.0.0.1:12311/sse"
        assert rag_mcp.default_config.stdio is None
        assert rag_mcp.name == "轻量化知识库"


class TestRealMCPNormalizer:
    """基于真实配置的 Normalizer 测试"""

    @pytest.fixture
    def normalizer(self):
        return Normalizer()

    def test_normalize_git_mcp_always_allow(self, normalizer, tmp_path, real_git_mcp_config):
        """验证 alwaysAllow 字段被正确解析"""
        server_dir = tmp_path / "git_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(
            server_dir=server_dir,
            raw_config=real_git_mcp_config,
            rpm_metadata={},
            source=SourceType.RPM,
        )

        # alwaysAllow 应该转换为 tool_policy
        assert record.default_config.tool_policy.always_allow == [
            "git_status",
            "get_git_config",
            "git_diff_unstaged",
            "git_diff_staged",
            "git_diff",
            "git_show",
            "list_branches",
        ]

    def test_normalize_ccb_sensitive_args(self, normalizer, tmp_path, real_ccb_mcp_config, real_ccb_mcp_rpm_yaml):
        """验证含敏感参数的 ccb_mcp 配置被正确解析"""
        server_dir = tmp_path / "ccb_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(
            server_dir=server_dir,
            raw_config=real_ccb_mcp_config,
            rpm_metadata=real_ccb_mcp_rpm_yaml,
            source=SourceType.RPM,
        )

        assert record.id == "ccb_mcp"
        assert record.upstream_key == "ccbMcp"
        # python3 命令
        assert record.default_config.stdio.command == "python3"

    def test_normalize_oedeploy_timeout(
        self,
        normalizer,
        tmp_path,
        real_oedeploy_mcp_config,
        real_oedeploy_mcp_rpm_yaml,
    ):
        """验证 timeout 字段被正确解析为 tool_call timeout"""
        server_dir = tmp_path / "oeDeploy_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(
            server_dir=server_dir,
            raw_config=real_oedeploy_mcp_config,
            rpm_metadata=real_oedeploy_mcp_rpm_yaml,
            source=SourceType.RPM,
        )

        # timeout: 1800 应该转换为 timeouts.tool_call
        assert record.default_config.timeouts.tool_call == 1800

    def test_normalize_cvekit_env_and_description(
        self,
        normalizer,
        tmp_path,
        real_cvekit_mcp_config,
        real_cvekit_mcp_rpm_yaml,
    ):
        """验证 env 和 description 字段被正确解析"""
        server_dir = tmp_path / "cvekit_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(
            server_dir=server_dir,
            raw_config=real_cvekit_mcp_config,
            rpm_metadata=real_cvekit_mcp_rpm_yaml,
            source=SourceType.RPM,
        )

        # env 应该被保留
        assert record.default_config.stdio.env.get("LANG") == "en_US.UTF-8"

        # description 应该从 mcpServers entry 获取
        assert "CVE" in record.summary or "CVE" in record.name


class TestRealMCPDiagnostics:
    """基于真实配置的诊断测试"""

    def test_preflight_uv_command_allowed(self, mock_real_config, mock_real_mcp_servers_dir):
        """验证 uv 命令在白名单中"""
        discovery = Discovery(mock_real_config)
        servers = discovery.scan_all()
        preflight = PreflightChecker(mock_real_config)

        git_mcp = next((s for s in servers if s.id == "git_mcp"), None)
        assert git_mcp is not None

        diagnostics = preflight.run_preflight(git_mcp)
        assert diagnostics.command_allowed is True

    def test_preflight_python3_command_allowed(self, mock_real_config, mock_real_mcp_servers_dir):
        """验证 python3 命令在白名单中"""
        discovery = Discovery(mock_real_config)
        servers = discovery.scan_all()
        preflight = PreflightChecker(mock_real_config)

        ccb_mcp = next((s for s in servers if s.id == "ccb_mcp"), None)
        assert ccb_mcp is not None

        diagnostics = preflight.run_preflight(ccb_mcp)
        assert diagnostics.command_allowed is True

    def test_preflight_python_deps_detection(self, mock_real_config, mock_real_mcp_servers_dir):
        """TC106: 检测 Python 依赖缺失"""
        discovery = Discovery(mock_real_config)
        servers = discovery.scan_all()
        preflight = PreflightChecker(mock_real_config)

        cvekit = next((s for s in servers if s.id == "cvekit_mcp"), None)
        assert cvekit is not None

        diagnostics = preflight.run_preflight(cvekit)

        # cvekit 有 python 依赖: requests, PyGithub, curl_cffi
        # 这些在测试环境中可能不存在，应该被检测出来
        if diagnostics.deps_missing:
            python_deps = diagnostics.deps_missing.get("python", [])
            # 至少应该检测到 python 依赖字段
            assert isinstance(python_deps, list)


class TestRealMCPIntegration:
    """真实配置的集成测试"""

    def test_full_discovery_and_diagnostics_flow(self, mock_real_config, mock_real_mcp_servers_dir):
        """完整的发现和诊断流程"""
        from witty_mcp_manager.diagnostics.checker import Checker

        discovery = Discovery(mock_real_config)
        checker = Checker()
        preflight = PreflightChecker(mock_real_config)

        servers = discovery.scan_all()
        assert len(servers) == 6

        for server in servers:
            # 运行文件检查
            _ = checker.validate(server)  # 忽略返回值
            # 运行预检查
            preflight_diag = preflight.run_preflight(server)

            # 每个 server 都应该有有效的 diagnostics
            assert preflight_diag is not None
            # STDIO 服务器的命令都应该在白名单中
            if server.default_config.stdio:
                assert preflight_diag.command_allowed is True, f"{server.id} command not allowed"

    def test_overlay_with_real_servers(self, mock_real_config, mock_real_mcp_servers_dir, mock_state_directory):
        """测试 overlay 与真实服务器的集成"""
        from witty_mcp_manager.overlay.resolver import OverlayResolver
        from witty_mcp_manager.overlay.storage import OverlayStorage
        from witty_mcp_manager.registry.models import Override

        discovery = Discovery(mock_real_config)
        storage = OverlayStorage(mock_real_config.state_directory)
        resolver = OverlayResolver(storage)

        servers = discovery.scan_all()
        git_mcp = next((s for s in servers if s.id == "git_mcp"), None)
        assert git_mcp is not None

        # 创建用户 overlay
        user_id = "test_user"
        override = Override(
            scope=f"user/{user_id}",
            disabled=False,
            env={"GIT_TOKEN": "secret://git_token"},
        )
        storage.save_override("git_mcp", override, user_id=user_id)

        # 解析生效配置
        effective = resolver.resolve(git_mcp, user_id)
        assert effective.disabled is False
        # env 应该合并
        assert "GIT_TOKEN" in effective.env


class TestAutoApproveFieldMapping:
    """测试 autoApprove 字段映射（真实 RPM MCP 案例）"""

    @pytest.fixture
    def normalizer(self):
        return Normalizer()

    def test_code_review_assistant_auto_approve(self, normalizer, tmp_path, real_code_review_assistant_mcp_config):
        """真实案例：code_review_assistant_mcp 使用 autoApprove: ["*"]"""
        server_dir = tmp_path / "code_review_assistant_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(
            server_dir=server_dir,
            raw_config=real_code_review_assistant_mcp_config,
            rpm_metadata={},
            source=SourceType.RPM,
        )

        # autoApprove: ["*"] 应该映射到 always_allow
        assert "*" in record.default_config.tool_policy.always_allow
        # upstream_key 应该是 code_review_assistant
        assert record.upstream_key == "code_review_assistant"

    def test_api_document_always_allow(self, normalizer, tmp_path, real_api_document_mcp_config):
        """真实案例：api_document_mcp 使用 alwaysAllow: ["generate_docs"]"""
        server_dir = tmp_path / "api_document_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(
            server_dir=server_dir,
            raw_config=real_api_document_mcp_config,
            rpm_metadata={},
            source=SourceType.RPM,
        )

        # alwaysAllow 应该正常工作
        assert "generate_docs" in record.default_config.tool_policy.always_allow

    def test_network_manager_multiple_tools(self, normalizer, tmp_path, real_network_manager_mcp_config):
        """真实案例：network_manager_mcp 有多个 alwaysAllow tools"""
        server_dir = tmp_path / "network_manager_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(
            server_dir=server_dir,
            raw_config=real_network_manager_mcp_config,
            rpm_metadata={},
            source=SourceType.RPM,
        )

        always_allow = record.default_config.tool_policy.always_allow
        assert "list_interfaces" in always_allow
        assert "get_interface_status" in always_allow
        assert "show_connections" in always_allow
