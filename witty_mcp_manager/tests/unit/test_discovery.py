"""Discovery 模块单元测试

测试用例：
- TC001: 扫描 /opt/mcp-servers/servers 成功识别 server 目录
- TC002: 解析 mcp_config.json（key≠目录名）
"""

import json
from pathlib import Path

import pytest

from witty_mcp_manager.registry.discovery import Discovery
from witty_mcp_manager.registry.models import SourceType, TransportType


class TestDiscovery:
    """Discovery 模块测试"""

    def test_scan_servers_success(self, mock_config, mock_mcp_servers_dir):
        """TC001: 扫描目录成功识别 server"""
        discovery = Discovery(mock_config)
        servers = discovery.scan_all()

        assert len(servers) == 2
        
        # 验证 git_mcp
        git_mcp = next((s for s in servers if s.id == "git_mcp"), None)
        assert git_mcp is not None
        assert git_mcp.name == "Git MCP Server"
        assert git_mcp.source == SourceType.RPM
        assert git_mcp.transport == TransportType.STDIO

    def test_scan_empty_directory(self, mock_config, tmp_path):
        """扫描空目录返回空列表"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        mock_config.scan_paths = [str(empty_dir)]
        discovery = Discovery(mock_config)
        servers = discovery.scan_all()

        assert servers == []

    def test_scan_nonexistent_directory(self, mock_config):
        """扫描不存在的目录返回空列表"""
        mock_config.scan_paths = ["/nonexistent/path"]
        discovery = Discovery(mock_config)
        servers = discovery.scan_all()

        assert servers == []

    def test_parse_server_with_rpm_metadata(self, mock_config, mock_mcp_servers_dir):
        """解析包含 mcp-rpm.yaml 的 server"""
        discovery = Discovery(mock_config)
        servers = discovery.scan_all()

        git_mcp = next((s for s in servers if s.id == "git_mcp"), None)
        assert git_mcp is not None
        assert git_mcp.rpm_metadata.get("name") == "git-mcp"
        assert "system" in git_mcp.rpm_metadata.get("dependencies", {})

    def test_parse_server_without_rpm_metadata(self, mock_config, mock_mcp_servers_dir):
        """解析不包含 mcp-rpm.yaml 的 server"""
        discovery = Discovery(mock_config)
        servers = discovery.scan_all()

        rpm_builder = next((s for s in servers if s.id == "rpm-builder_mcp"), None)
        assert rpm_builder is not None
        assert rpm_builder.rpm_metadata == {}

    def test_skip_hidden_directories(self, mock_config, mock_mcp_servers_dir):
        """跳过隐藏目录"""
        # 创建隐藏目录
        hidden_dir = mock_mcp_servers_dir / ".hidden_mcp"
        hidden_dir.mkdir()
        (hidden_dir / "mcp_config.json").write_text('{"mcpServers": {"test": {}}}')

        discovery = Discovery(mock_config)
        servers = discovery.scan_all()

        # 应该不包含隐藏目录
        assert not any(s.id == ".hidden_mcp" for s in servers)

    def test_skip_invalid_json(self, mock_config, mock_mcp_servers_dir):
        """跳过无效 JSON 配置"""
        # 创建无效 JSON 的 server
        invalid_mcp = mock_mcp_servers_dir / "invalid_mcp"
        invalid_mcp.mkdir()
        (invalid_mcp / "mcp_config.json").write_text("invalid json {")

        discovery = Discovery(mock_config)
        servers = discovery.scan_all()

        # 应该不包含无效配置的 server
        assert not any(s.id == "invalid_mcp" for s in servers)
        # 但其他 server 应该正常
        assert len(servers) == 2

    def test_upstream_key_different_from_dir_name(self, mock_config, tmp_path):
        """TC002: upstream_key 与目录名不一致的情况"""
        servers_dir = tmp_path / "servers2"  # 使用不同的目录名避免冲突
        servers_dir.mkdir(exist_ok=True)

        # 目录名是 oeDeploy_mcp，但 key 是 mcp-oedp
        oedp = servers_dir / "oeDeploy_mcp"
        oedp.mkdir(exist_ok=True)
        config = {
            "mcpServers": {
                "mcp-oedp": {  # key 与目录名不一致
                    "command": "uv",
                    "args": ["run", "server.py"],
                }
            },
            "name": "oeDeploy MCP",
        }
        (oedp / "mcp_config.json").write_text(json.dumps(config))
        (oedp / "src").mkdir()

        mock_config.scan_paths = [str(servers_dir)]
        discovery = Discovery(mock_config)
        servers = discovery.scan_all()

        assert len(servers) == 1
        server = servers[0]
        
        # canonical id 应该是目录名
        assert server.id == "oeDeploy_mcp"
        # upstream_key 是配置中的 key
        assert server.upstream_key == "mcp-oedp"


class TestDiscoveryAdminSources:
    """Admin Sources 注册测试"""

    def test_register_admin_source_sse(self, mock_config):
        """注册 SSE 类型的 admin source"""
        from witty_mcp_manager.config.config import AdminSource

        mock_config.admin_sources = [
            AdminSource(
                id="oe-cli-mcp-server",
                name="oe-智能运维工具",
                transport="sse",
                sse={
                    "url": "http://127.0.0.1:12555/sse",
                    "headers": {},
                    "timeout": 60,
                },
                description="文件管理，软件包管理",
            )
        ]

        discovery = Discovery(mock_config)
        servers = discovery.scan_all()

        # 应该包含 admin source
        admin_server = next((s for s in servers if s.id == "oe-cli-mcp-server"), None)
        assert admin_server is not None
        assert admin_server.source == SourceType.ADMIN
        assert admin_server.transport == TransportType.SSE
        assert admin_server.default_config.sse.url == "http://127.0.0.1:12555/sse"

    def test_get_server_by_id(self, mock_config, mock_mcp_servers_dir):
        """根据 ID 获取 server"""
        discovery = Discovery(mock_config)

        server = discovery.get_server_by_id("git_mcp")
        assert server is not None
        assert server.id == "git_mcp"

        # 不存在的 ID
        server = discovery.get_server_by_id("nonexistent")
        assert server is None
