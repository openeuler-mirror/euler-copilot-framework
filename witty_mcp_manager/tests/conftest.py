"""Witty MCP Manager 测试配置"""

import json

import pytest


@pytest.fixture
def sample_mcp_config():
    """示例 mcp_config.json 内容"""
    return {
        "mcpServers": {
            "git_mcp": {
                "command": "uv",
                "args": [
                    "--directory",
                    "/opt/mcp-servers/servers/git_mcp/src",
                    "run",
                    "git_mcp.py",
                ],
                "disabled": False,
                "alwaysAllow": [
                    "git_status",
                    "get_git_config",
                    "git_diff_unstaged",
                ],
            }
        },
        "name": "Git MCP Server",
        "description": "Git 仓库管理工具",
        "mcpType": "stdio",
    }


@pytest.fixture
def sample_mcp_rpm_yaml():
    """示例 mcp-rpm.yaml 内容"""
    return {
        "name": "git-mcp",
        "summary": "MCP server for Git repository operations",
        "description": "Provides MCP tools for Git operations",
        "dependencies": {
            "system": ["python3", "uv"],
            "packages": ["git", "jq"],
        },
        "files": {
            "required": ["mcp_config.json", "src/git_mcp.py"],
            "optional": ["README.md"],
        },
    }


@pytest.fixture
def sample_sse_config():
    """示例 SSE 类型配置"""
    return {
        "mcpServers": {
            "rag_mcp": {
                "url": "http://127.0.0.1:12311/sse",
                "headers": {},
                "timeout": 60,
            }
        },
        "name": "RAG MCP Server",
        "description": "文档问答服务",
        "mcpType": "sse",
    }


@pytest.fixture
def mock_mcp_servers_dir(tmp_path, sample_mcp_config, sample_mcp_rpm_yaml):
    """创建模拟的 /opt/mcp-servers/servers 目录"""
    servers_dir = tmp_path / "servers"
    servers_dir.mkdir()

    # 创建 git_mcp
    git_mcp = servers_dir / "git_mcp"
    git_mcp.mkdir()
    (git_mcp / "mcp_config.json").write_text(json.dumps(sample_mcp_config, indent=2))

    import yaml

    (git_mcp / "mcp-rpm.yaml").write_text(yaml.dump(sample_mcp_rpm_yaml))

    src_dir = git_mcp / "src"
    src_dir.mkdir()
    (src_dir / "git_mcp.py").write_text("# Git MCP Server entry point")

    # 创建 rpm_builder_mcp（无 mcp-rpm.yaml）
    rpm_builder = servers_dir / "rpm-builder_mcp"
    rpm_builder.mkdir()
    rpm_config = {
        "mcpServers": {
            "rpm-builder_mcp": {
                "command": "uv",
                "args": ["--directory", "/opt/mcp-servers/servers/rpm-builder_mcp/src", "run", "server.py"],
            }
        },
        "name": "RPM Builder MCP",
    }
    (rpm_builder / "mcp_config.json").write_text(json.dumps(rpm_config, indent=2))
    (rpm_builder / "src").mkdir()
    (rpm_builder / "src" / "server.py").write_text("# RPM Builder entry")

    return servers_dir


@pytest.fixture
def mock_state_directory(tmp_path):
    """创建模拟的 StateDirectory"""
    state_dir = tmp_path / "witty-mcp-manager"
    state_dir.mkdir()
    (state_dir / "overrides" / "global").mkdir(parents=True)
    (state_dir / "overrides" / "users").mkdir(parents=True)
    (state_dir / "cache").mkdir()
    (state_dir / "runtime").mkdir()
    return state_dir


@pytest.fixture
def mock_config(mock_mcp_servers_dir, mock_state_directory):
    """创建模拟配置"""
    from witty_mcp_manager.config.config import ManagerConfig

    return ManagerConfig(
        scan_paths=[str(mock_mcp_servers_dir)],
        state_directory=str(mock_state_directory),
        runtime_directory=str(mock_state_directory / "runtime"),
        socket_path=str(mock_state_directory / "mcp-manager.sock"),
        command_allowlist=["uv", "python3", "python", "node", "npx"],
    )
