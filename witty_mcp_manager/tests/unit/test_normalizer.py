"""Normalizer 模块单元测试

测试场景分类：
1. 标准格式处理：Claude Desktop/Cline 事实标准配置
2. Admin 私有格式兼容：euler-copilot-framework mcp_center 私有格式
3. 边界条件处理：空配置、缺失字段等

配置格式参考：
- 标准格式: https://docs.cline.bot/mcp/configuring-mcp-servers
- MCP 协议: https://modelcontextprotocol.io/specification/latest/basic/transports
"""

import pytest

from witty_mcp_manager.registry.models import SourceType, TransportType
from witty_mcp_manager.registry.normalizer import Normalizer


class TestStandardFormatNormalization:
    """标准格式（Claude Desktop/Cline 事实标准）处理测试"""

    @pytest.fixture
    def normalizer(self):
        return Normalizer()

    def test_stdio_config_with_always_allow(self, normalizer, tmp_path, sample_stdio_config):
        """标准 STDIO 配置 - 使用 alwaysAllow 字段"""
        server_dir = tmp_path / "filesystem"
        server_dir.mkdir()

        record = normalizer.normalize(
            server_dir=server_dir,
            raw_config=sample_stdio_config,
            rpm_metadata={},
            source=SourceType.RPM,
        )

        assert record is not None
        assert record.id == "filesystem"
        assert record.transport == TransportType.STDIO
        assert record.default_config.stdio is not None
        assert record.default_config.stdio.command == "npx"
        assert record.default_config.sse is None
        # 验证 alwaysAllow 正确解析
        assert "read_file" in record.default_config.tool_policy.always_allow
        assert "list_directory" in record.default_config.tool_policy.always_allow

    def test_sse_config_with_always_allow(self, normalizer, tmp_path, sample_sse_config):
        """标准 SSE 配置 - 使用 alwaysAllow 字段"""
        server_dir = tmp_path / "remote-server"
        server_dir.mkdir()

        record = normalizer.normalize(
            server_dir=server_dir,
            raw_config=sample_sse_config,
            rpm_metadata={},
            source=SourceType.RPM,
        )

        assert record is not None
        assert record.transport == TransportType.SSE
        assert record.default_config.sse is not None
        assert record.default_config.sse.url == "https://api.example.com/mcp"
        assert record.default_config.sse.headers == {"Authorization": "Bearer token"}
        assert record.default_config.stdio is None
        assert "query" in record.default_config.tool_policy.always_allow

    def test_transport_detection_from_config_fields(self, normalizer, tmp_path):
        """从配置字段推断传输类型（无 mcpType 声明）"""
        server_dir = tmp_path / "test_mcp"
        server_dir.mkdir()

        # url 字段 -> SSE
        config = {"mcpServers": {"test": {"url": "http://localhost/sse"}}}
        record = normalizer.normalize(server_dir, config, {}, SourceType.RPM)
        assert record.transport == TransportType.SSE

        # command 字段 -> STDIO
        config = {"mcpServers": {"test": {"command": "node"}}}
        record = normalizer.normalize(server_dir, config, {}, SourceType.RPM)
        assert record.transport == TransportType.STDIO

    def test_preserve_unknown_extras(self, normalizer, tmp_path):
        """保留未知扩展字段到 extras"""
        server_dir = tmp_path / "test_mcp"
        server_dir.mkdir()

        config = {
            "mcpServers": {
                "test": {
                    "command": "uv",
                    "customField": "custom_value",
                    "anotherExtra": 123,
                },
            },
        }

        record = normalizer.normalize(server_dir, config, {}, SourceType.RPM)

        assert "customField" in record.default_config.extras
        assert record.default_config.extras["customField"] == "custom_value"
        assert record.default_config.extras["anotherExtra"] == 123


class TestAdminPrivateFormatCompatibility:
    """Admin 私有格式（euler-copilot-framework mcp_center）兼容性测试"""

    @pytest.fixture
    def normalizer(self):
        return Normalizer()

    def test_auto_approve_maps_to_always_allow(self, normalizer, tmp_path, admin_sse_config):
        """Admin 私有格式 autoApprove 字段映射到 always_allow"""
        server_dir = tmp_path / "example_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(server_dir, admin_sse_config, {}, SourceType.ADMIN)

        # autoApprove: ["tool_a", "tool_b"] 应该映射到 always_allow
        assert "tool_a" in record.default_config.tool_policy.always_allow
        assert "tool_b" in record.default_config.tool_policy.always_allow

    def test_auto_install_ignored(self, normalizer, tmp_path, real_rag_mcp_config):
        """Admin 私有字段 autoInstall 被忽略（不放入 extras）"""
        server_dir = tmp_path / "rag_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(server_dir, real_rag_mcp_config, {}, SourceType.ADMIN)

        # autoInstall 是旧 Loader 专用字段，不应出现在 extras 中
        assert "autoInstall" not in record.default_config.extras
        # autoApprove 也不应出现在 extras 中
        assert "autoApprove" not in record.default_config.extras

    def test_mcp_type_for_transport_detection(self, normalizer, tmp_path):
        """Admin 私有字段 mcpType 用于传输类型检测"""
        server_dir = tmp_path / "test_mcp"
        server_dir.mkdir()

        # mcpType: "sse" 显式声明 SSE
        config = {
            "mcpServers": {"test": {"url": "http://localhost:8080/sse"}},
            "mcpType": "sse",
        }
        record = normalizer.normalize(server_dir, config, {}, SourceType.ADMIN)
        assert record.transport == TransportType.SSE

        # mcpType: "stdio" 显式声明 STDIO
        config = {
            "mcpServers": {"test": {"command": "python3"}},
            "mcpType": "stdio",
        }
        record = normalizer.normalize(server_dir, config, {}, SourceType.ADMIN)
        assert record.transport == TransportType.STDIO

    def test_always_allow_priority_over_auto_approve(self, normalizer, tmp_path):
        """标准 alwaysAllow 优先于私有 autoApprove"""
        server_dir = tmp_path / "test_mcp"
        server_dir.mkdir()

        config = {
            "mcpServers": {
                "test": {
                    "command": "python3",
                    "alwaysAllow": ["tool_a", "tool_b"],  # 标准字段
                    "autoApprove": ["tool_c"],  # 私有字段，应被忽略
                },
            },
        }

        record = normalizer.normalize(server_dir, config, {}, SourceType.RPM)

        # alwaysAllow 优先
        assert "tool_a" in record.default_config.tool_policy.always_allow
        assert "tool_b" in record.default_config.tool_policy.always_allow
        # autoApprove 被忽略
        assert "tool_c" not in record.default_config.tool_policy.always_allow


class TestRealVmConfigs:
    """真实 VM 配置测试（来自 openEuler 24.03 LTS SP3）"""

    @pytest.fixture
    def normalizer(self):
        return Normalizer()

    def test_real_git_mcp_standard_format(self, normalizer, tmp_path, real_git_mcp_config):
        """真实 git_mcp 配置（标准格式 + alwaysAllow）"""
        server_dir = tmp_path / "git_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(server_dir, real_git_mcp_config, {}, SourceType.RPM)

        assert record.id == "git_mcp"
        assert record.transport == TransportType.STDIO
        assert record.default_config.stdio.command == "uv"
        # 验证 alwaysAllow 正确解析
        assert "git_status" in record.default_config.tool_policy.always_allow
        assert "git_diff" in record.default_config.tool_policy.always_allow

    def test_real_code_review_assistant_auto_approve(self, normalizer, tmp_path, real_code_review_assistant_mcp_config):
        """真实 code_review_assistant_mcp 配置（RPM MCP 但使用非标准 autoApprove）"""
        server_dir = tmp_path / "code_review_assistant_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(server_dir, real_code_review_assistant_mcp_config, {}, SourceType.RPM)

        # autoApprove: ["*"] 应该映射到 always_allow
        assert "*" in record.default_config.tool_policy.always_allow

    def test_real_admin_rag_mcp_private_format(self, normalizer, tmp_path, real_rag_mcp_config):
        """真实 Admin rag_mcp 配置（私有 SSE 格式）"""
        server_dir = tmp_path / "rag_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(server_dir, real_rag_mcp_config, {}, SourceType.ADMIN)

        assert record.id == "rag_mcp"
        assert record.transport == TransportType.SSE
        assert record.default_config.sse.url == "http://127.0.0.1:12311/sse"
        # Admin MCP 使用 autoApprove: []
        assert record.default_config.tool_policy.always_allow == []


class TestEdgeCases:
    """边界条件测试"""

    @pytest.fixture
    def normalizer(self):
        return Normalizer()

    def test_empty_mcp_servers(self, normalizer, tmp_path):
        """空 mcpServers 返回 None"""
        server_dir = tmp_path / "empty_mcp"
        server_dir.mkdir()

        config = {"mcpServers": {}}
        record = normalizer.normalize(server_dir, config, {}, SourceType.RPM)

        assert record is None

    def test_missing_mcp_servers(self, normalizer, tmp_path):
        """缺少 mcpServers 返回 None"""
        server_dir = tmp_path / "no_servers"
        server_dir.mkdir()

        config = {"name": "Test"}
        record = normalizer.normalize(server_dir, config, {}, SourceType.RPM)

        assert record is None

    def test_rpm_metadata_integration(self, normalizer, tmp_path, sample_mcp_config, sample_mcp_rpm_yaml):
        """RPM 元数据集成"""
        server_dir = tmp_path / "git_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(server_dir, sample_mcp_config, sample_mcp_rpm_yaml, SourceType.RPM)

        # rpm_metadata 应该被保存
        assert record.rpm_metadata == sample_mcp_rpm_yaml
        assert record.rpm_metadata["name"] == "git-mcp"
