"""Admin MCP 测试

测试基于 euler-copilot-framework mcp_center 的真实 admin MCP 配置：
- rag_mcp: 轻量化知识库（SSE）
- mcp_server_mcp: oe-智能运维工具（SSE）
"""

import json


class TestAdminMCPConfigs:
    """测试 admin MCP 配置格式"""

    def test_rag_mcp_config_structure(self, real_rag_mcp_config):
        """验证 rag_mcp 配置结构"""
        assert "mcpServers" in real_rag_mcp_config
        assert "rag_mcp" in real_rag_mcp_config["mcpServers"]

        server = real_rag_mcp_config["mcpServers"]["rag_mcp"]
        assert "url" in server
        assert "headers" in server
        assert "timeout" in server
        assert server["autoInstall"] is True

    def test_mcp_server_mcp_config_structure(self, real_mcp_server_mcp_config):
        """验证 mcp_server_mcp 配置结构"""
        assert "mcpServers" in real_mcp_server_mcp_config
        assert "mcp_server_mcp" in real_mcp_server_mcp_config["mcpServers"]

        server = real_mcp_server_mcp_config["mcpServers"]["mcp_server_mcp"]
        assert server["url"] == "http://127.0.0.1:12555/sse"
        assert server["timeout"] == 60

    def test_admin_mcp_is_sse_type(self, real_rag_mcp_config, real_mcp_server_mcp_config):
        """验证 admin MCP 都是 SSE 类型"""
        assert real_rag_mcp_config["mcpType"] == "sse"
        assert real_mcp_server_mcp_config["mcpType"] == "sse"

    def test_admin_mcp_has_metadata(self, real_rag_mcp_config, real_mcp_server_mcp_config):
        """验证 admin MCP 有名称和描述"""
        assert real_rag_mcp_config["name"] == "轻量化知识库"
        assert "overview" in real_rag_mcp_config
        assert "description" in real_rag_mcp_config

        assert real_mcp_server_mcp_config["name"] == "oe-智能运维工具"
        assert "文件管理" in real_mcp_server_mcp_config["overview"]


class TestAdminMCPDirectory:
    """测试 admin MCP 目录结构"""

    def test_mock_admin_dir_structure(self, mock_admin_mcp_dir):
        """验证 mock admin MCP 目录结构"""
        assert mock_admin_mcp_dir.exists()
        assert (mock_admin_mcp_dir / "rag_mcp").is_dir()
        assert (mock_admin_mcp_dir / "mcp_server_mcp").is_dir()
        assert (mock_admin_mcp_dir / "mcp_to_app_config.toml").is_file()

    def test_rag_mcp_config_file(self, mock_admin_mcp_dir):
        """验证 rag_mcp config.json 文件存在且有效"""
        config_path = mock_admin_mcp_dir / "rag_mcp" / "config.json"
        assert config_path.exists()

        config = json.loads(config_path.read_text())
        assert "mcpServers" in config
        assert config["mcpType"] == "sse"

    def test_mcp_server_mcp_config_file(self, mock_admin_mcp_dir):
        """验证 mcp_server_mcp config.json 文件"""
        config_path = mock_admin_mcp_dir / "mcp_server_mcp" / "config.json"
        assert config_path.exists()

        config = json.loads(config_path.read_text())
        assert "mcp_server_mcp" in config["mcpServers"]


class TestSSEServerRecord:
    """测试 SSE ServerRecord 创建"""

    def test_sse_record_transport(self, mock_sse_server_record):
        """验证 SSE record 传输类型"""
        from witty_mcp_manager.registry.models import TransportType

        assert mock_sse_server_record.transport == TransportType.SSE

    def test_sse_record_source(self, mock_sse_server_record):
        """验证 SSE record 来源类型"""
        from witty_mcp_manager.registry.models import SourceType

        assert mock_sse_server_record.source == SourceType.ADMIN

    def test_sse_record_config(self, mock_sse_server_record):
        """验证 SSE record 配置"""
        config = mock_sse_server_record.default_config
        assert config.sse is not None
        assert config.sse.url == "http://127.0.0.1:12311/sse"

    def test_mcp_server_record(self, mock_mcp_server_record):
        """验证 mcp_server_mcp record"""
        from witty_mcp_manager.registry.models import SourceType, TransportType

        assert mock_mcp_server_record.id == "mcp_server_mcp"
        assert mock_mcp_server_record.transport == TransportType.SSE
        assert mock_mcp_server_record.source == SourceType.ADMIN
        assert mock_mcp_server_record.default_config.sse.url == "http://127.0.0.1:12555/sse"


class TestSSEAdapter:
    """测试 SSE Adapter 与 admin MCP"""

    def test_create_sse_adapter_from_rag_config(self, mock_sse_server_record):
        """测试从 rag_mcp 配置创建 SSE adapter"""
        from unittest.mock import MagicMock

        from witty_mcp_manager.adapters import SSEAdapter
        from witty_mcp_manager.overlay.resolver import EffectiveConfig

        effective_config = MagicMock(spec=EffectiveConfig)
        effective_config.mcp_id = mock_sse_server_record.id
        effective_config.config = mock_sse_server_record.default_config
        effective_config.config.sse = mock_sse_server_record.default_config.sse
        effective_config.timeouts = mock_sse_server_record.default_config.timeouts
        effective_config.headers = {}

        adapter = SSEAdapter(
            server=mock_sse_server_record,
            config=effective_config,
        )
        assert adapter.mcp_id == "rag_mcp"
        assert not adapter.is_connected

    def test_create_sse_adapter_from_mcp_server_config(self, mock_mcp_server_record):
        """测试从 mcp_server_mcp 配置创建 SSE adapter"""
        from unittest.mock import MagicMock

        from witty_mcp_manager.adapters import SSEAdapter
        from witty_mcp_manager.overlay.resolver import EffectiveConfig

        effective_config = MagicMock(spec=EffectiveConfig)
        effective_config.mcp_id = mock_mcp_server_record.id
        effective_config.config = mock_mcp_server_record.default_config
        effective_config.config.sse = mock_mcp_server_record.default_config.sse
        effective_config.timeouts = mock_mcp_server_record.default_config.timeouts
        effective_config.headers = {}

        adapter = SSEAdapter(
            server=mock_mcp_server_record,
            config=effective_config,
        )
        assert adapter.mcp_id == "mcp_server_mcp"


class TestAdminMCPVsRPMMCP:
    """对比测试 admin MCP 和 RPM MCP 的差异"""

    def test_source_type_difference(self, mock_server_record, mock_sse_server_record):
        """验证来源类型差异"""
        from witty_mcp_manager.registry.models import SourceType

        # RPM MCP
        assert mock_server_record.source == SourceType.RPM
        # Admin MCP
        assert mock_sse_server_record.source == SourceType.ADMIN

    def test_transport_type_difference(self, mock_server_record, mock_sse_server_record):
        """验证传输类型差异"""
        from witty_mcp_manager.registry.models import TransportType

        # RPM MCP typically uses STDIO
        assert mock_server_record.transport == TransportType.STDIO
        # Admin MCP typically uses SSE
        assert mock_sse_server_record.transport == TransportType.SSE

    def test_config_structure_difference(self, mock_server_record, mock_sse_server_record):
        """验证配置结构差异"""
        # RPM MCP has stdio config
        assert mock_server_record.default_config.stdio is not None
        assert mock_server_record.default_config.sse is None

        # Admin MCP has sse config
        assert mock_sse_server_record.default_config.sse is not None
        assert mock_sse_server_record.default_config.stdio is None

    def test_rpm_metadata_only_for_rpm(self, mock_server_record, mock_sse_server_record):
        """验证只有 RPM MCP 有 rpm_metadata"""
        assert mock_server_record.rpm_metadata is not None
        assert len(mock_server_record.rpm_metadata) > 0
        # Admin MCP 的 rpm_metadata 为空 dict
        assert mock_sse_server_record.rpm_metadata == {}


class TestAutoApproveAndAutoInstall:
    """测试 admin MCP 的 autoApprove 和 autoInstall 特性"""

    def test_auto_install_enabled(self, real_rag_mcp_config):
        """验证 autoInstall 默认启用"""
        server = real_rag_mcp_config["mcpServers"]["rag_mcp"]
        assert server["autoInstall"] is True

    def test_auto_approve_empty_by_default(self, real_rag_mcp_config):
        """验证 autoApprove 默认为空列表"""
        server = real_rag_mcp_config["mcpServers"]["rag_mcp"]
        assert server["autoApprove"] == []

    def test_tool_policy_always_allow(self, mock_sse_server_record):
        """验证 tool policy 中的 always_allow"""
        policy = mock_sse_server_record.default_config.tool_policy
        assert policy.always_allow == []

    def test_tool_policy_auto_discover(self, mock_sse_server_record):
        """验证 tool policy 中的 auto_discover"""
        policy = mock_sse_server_record.default_config.tool_policy
        assert policy.auto_discover is True
