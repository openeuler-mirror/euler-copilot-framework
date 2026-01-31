"""Normalizer 模块单元测试

测试用例：
- 配置标准化
- 传输类型检测
- 扩展字段保留
"""

import pytest

from witty_mcp_manager.registry.models import SourceType, TransportType
from witty_mcp_manager.registry.normalizer import Normalizer


class TestNormalizer:
    """Normalizer 模块测试"""

    @pytest.fixture
    def normalizer(self):
        return Normalizer()

    def test_normalize_stdio_config(self, normalizer, tmp_path, sample_mcp_config):
        """标准化 STDIO 配置"""
        server_dir = tmp_path / "git_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(
            server_dir=server_dir,
            raw_config=sample_mcp_config,
            rpm_metadata={},
            source=SourceType.RPM,
        )

        assert record is not None
        assert record.id == "git_mcp"
        assert record.transport == TransportType.STDIO
        assert record.default_config.stdio is not None
        assert record.default_config.stdio.command == "uv"
        assert record.default_config.sse is None

    def test_normalize_sse_config(self, normalizer, tmp_path, sample_sse_config):
        """标准化 SSE 配置"""
        server_dir = tmp_path / "rag_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(
            server_dir=server_dir,
            raw_config=sample_sse_config,
            rpm_metadata={},
            source=SourceType.RPM,
        )

        assert record is not None
        assert record.id == "rag_mcp"
        assert record.transport == TransportType.SSE
        assert record.default_config.sse is not None
        assert record.default_config.sse.url == "http://127.0.0.1:12311/sse"
        assert record.default_config.stdio is None

    def test_detect_transport_from_mcp_type(self, normalizer, tmp_path):
        """从 mcpType 字段检测传输类型"""
        server_dir = tmp_path / "test_mcp"
        server_dir.mkdir()

        # 显式 SSE
        config = {
            "mcpServers": {"test": {"url": "http://localhost:8080/sse"}},
            "mcpType": "sse",
        }
        record = normalizer.normalize(server_dir, config, {}, SourceType.RPM)
        assert record.transport == TransportType.SSE

        # 显式 STDIO
        config = {
            "mcpServers": {"test": {"command": "python3"}},
            "mcpType": "stdio",
        }
        record = normalizer.normalize(server_dir, config, {}, SourceType.RPM)
        assert record.transport == TransportType.STDIO

    def test_detect_transport_from_config_fields(self, normalizer, tmp_path):
        """从配置字段推断传输类型"""
        server_dir = tmp_path / "test_mcp"
        server_dir.mkdir()

        # 有 url 字段 -> SSE
        config = {"mcpServers": {"test": {"url": "http://localhost/sse"}}}
        record = normalizer.normalize(server_dir, config, {}, SourceType.RPM)
        assert record.transport == TransportType.SSE

        # 有 command 字段 -> STDIO
        config = {"mcpServers": {"test": {"command": "node"}}}
        record = normalizer.normalize(server_dir, config, {}, SourceType.RPM)
        assert record.transport == TransportType.STDIO

    def test_preserve_extras(self, normalizer, tmp_path):
        """保留未知扩展字段"""
        server_dir = tmp_path / "test_mcp"
        server_dir.mkdir()

        config = {
            "mcpServers": {
                "test": {
                    "command": "uv",
                    "customField": "custom_value",
                    "anotherExtra": 123,
                }
            },
        }

        record = normalizer.normalize(server_dir, config, {}, SourceType.RPM)

        assert "customField" in record.default_config.extras
        assert record.default_config.extras["customField"] == "custom_value"
        assert record.default_config.extras["anotherExtra"] == 123

    def test_always_allow_tools(self, normalizer, tmp_path, sample_mcp_config):
        """解析 alwaysAllow 字段"""
        server_dir = tmp_path / "git_mcp"
        server_dir.mkdir()

        record = normalizer.normalize(server_dir, sample_mcp_config, {}, SourceType.RPM)

        assert "git_status" in record.default_config.tool_policy.always_allow
        assert "get_git_config" in record.default_config.tool_policy.always_allow

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
        """集成 RPM 元数据"""
        server_dir = tmp_path / "git_mcp"
        server_dir.mkdir(exist_ok=True)

        record = normalizer.normalize(server_dir, sample_mcp_config, sample_mcp_rpm_yaml, SourceType.RPM)

        # summary 优先从 raw_config.description 获取，如果没有则从 rpm_metadata.summary 获取
        # sample_mcp_config 有 description，所以用它
        assert record.summary == sample_mcp_config.get("description", sample_mcp_rpm_yaml["summary"])
        # rpm_metadata 应该被保存
        assert record.rpm_metadata == sample_mcp_rpm_yaml
