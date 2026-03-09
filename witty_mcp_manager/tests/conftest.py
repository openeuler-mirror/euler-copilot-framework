"""Witty MCP Manager 测试配置

Fixtures 分类：
1. 标准格式 Fixtures (sample_*): 符合 Claude Desktop/Cline 事实标准的配置
2. Admin 私有格式 Fixtures (admin_*): euler-copilot-framework mcp_center 私有格式
3. 真实 VM Fixtures (real_*): 来自 openEuler 24.03 LTS SP3 VM 的真实配置

配置格式参考:
- 标准格式: https://docs.cline.bot/mcp/configuring-mcp-servers
- MCP 协议: https://modelcontextprotocol.io/specification/latest/basic/transports

关键区别:
- 标准格式使用 alwaysAllow，Admin 私有格式使用 autoApprove
- Admin 私有格式包含 autoInstall、mcpType、overview 等非标准字段
"""

import json

import pytest

# ============================================================================
# 标准格式 Fixtures（符合 Claude Desktop/Cline 事实标准）
# 参考: https://docs.cline.bot/mcp/configuring-mcp-servers
# ============================================================================


@pytest.fixture
def sample_stdio_config():
    """标准 STDIO 配置（Claude Desktop/Cline 格式）

    标准字段:
    - command: 启动命令
    - args: 命令参数
    - env: 环境变量（可选）
    - alwaysAllow: 无需确认的工具列表
    - disabled: 是否禁用
    """
    return {
        "mcpServers": {
            "filesystem": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "/home/user/documents",
                ],
                "env": {},
                "alwaysAllow": ["read_file", "list_directory"],
                "disabled": False,
            },
        },
    }


@pytest.fixture
def sample_sse_config():
    """标准 SSE 配置（Claude Desktop/Cline 格式）

    标准字段:
    - url: SSE 服务 URL
    - headers: HTTP 请求头
    - alwaysAllow: 无需确认的工具列表
    - disabled: 是否禁用
    """
    return {
        "mcpServers": {
            "remote-server": {
                "url": "https://api.example.com/mcp",
                "headers": {"Authorization": "Bearer token"},
                "alwaysAllow": ["query"],
                "disabled": False,
            },
        },
    }


@pytest.fixture
def sample_mcp_config():
    """标准 STDIO 配置（兼容旧测试，实际使用标准格式）"""
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
                    "git_diff_staged",
                    "git_diff",
                    "git_show",
                    "list_branches",
                ],
            },
        },
    }


@pytest.fixture
def sample_mcp_rpm_yaml():
    """mcp-rpm.yaml 元数据格式"""
    return {
        "name": "git-mcp",
        "summary": "MCP server for Git repository operations",
        "description": (
            "Provides MCP tools for interacting with Git repositories,\n"
            "including clone, pull, push and branch management.\n"
        ),
        "dependencies": {
            "system": ["python3", "uv", "python3-mcp", "jq"],
            "packages": ["git", "oegitext"],
        },
        "files": {
            "required": ["mcp_config.json", "src/git_mcp.py"],
            "optional": ["src/requirements.txt", "README.md"],
        },
    }


# ============================================================================
# Admin 私有格式 Fixtures（euler-copilot-framework mcp_center 专用）
# 与标准格式的差异:
# - autoApprove: 私有字段，等效于标准 alwaysAllow
# - autoInstall: 私有字段，Witty 忽略
# - mcpType: 私有字段，显式声明传输类型
# - name/overview/description: 顶层元数据
# ============================================================================


@pytest.fixture
def admin_sse_config():
    """Admin MCP 私有 SSE 配置示例

    注意：这是 euler-copilot-framework 的私有格式，不是 MCP 标准格式
    """
    return {
        "mcpServers": {
            "example_mcp": {
                "headers": {},
                "autoApprove": ["tool_a", "tool_b"],  # 私有字段，映射到 alwaysAllow
                "autoInstall": True,  # 私有字段，Witty 忽略
                "timeout": 60,
                "url": "http://127.0.0.1:8080/sse",
            },
        },
        "name": "Example Admin MCP",
        "overview": "示例 Admin MCP",  # 私有字段
        "description": "这是一个 Admin MCP 私有格式示例",
        "mcpType": "sse",  # 私有字段
    }


@pytest.fixture
def mock_mcp_servers_dir(tmp_path, sample_mcp_config, sample_mcp_rpm_yaml):
    """创建模拟的 /opt/mcp-servers/servers 目录（RPM MCP 标准格式）"""
    import yaml

    servers_dir = tmp_path / "servers"
    servers_dir.mkdir()

    # git_mcp（标准格式，mcp_config.json）
    git_mcp = servers_dir / "git_mcp"
    git_mcp.mkdir()
    (git_mcp / "mcp_config.json").write_text(json.dumps(sample_mcp_config, indent=2))
    (git_mcp / "mcp-rpm.yaml").write_text(yaml.dump(sample_mcp_rpm_yaml))
    (git_mcp / "src").mkdir()
    (git_mcp / "src" / "git_mcp.py").write_text("# Git MCP Server")

    # rpm-builder_mcp（标准格式，无 mcp-rpm.yaml）
    rpm_builder = servers_dir / "rpm-builder_mcp"
    rpm_builder.mkdir()
    rpm_config = {
        "mcpServers": {
            "rpm-builder_mcp": {
                "command": "uv",
                "args": ["--directory", "/opt/mcp-servers/servers/rpm-builder_mcp/src", "run", "server.py"],
                "alwaysAllow": [],
            },
        },
    }
    (rpm_builder / "mcp_config.json").write_text(json.dumps(rpm_config, indent=2))
    (rpm_builder / "src").mkdir()
    (rpm_builder / "src" / "server.py").write_text("# RPM Builder")

    return servers_dir


@pytest.fixture
def mock_mcp_center_dir(tmp_path):
    """创建模拟的 /usr/lib/sysagent/mcp_center/mcp_config 目录

    真实 VM 路径: /lib/sysagent/mcp_center/mcp_config/
    目录内容:
      mcp_server_mcp/config.json  (SSE)
      rag_mcp/config.json         (SSE)
      change.py                   (非 MCP 目录，应被跳过)
      mcp_to_app_config.toml      (文件，应被跳过)
    """
    mcp_center = tmp_path / "mcp_config"
    mcp_center.mkdir()

    # mcp_server_mcp（SSE，config.json 格式）
    mcp_server = mcp_center / "mcp_server_mcp"
    mcp_server.mkdir()
    mcp_server_config = {
        "mcpServers": {
            "mcp_server_mcp": {
                "headers": {},
                "autoApprove": [],
                "autoInstall": True,
                "timeout": 60,
                "url": "http://127.0.0.1:12555/sse",
            },
        },
        "name": "oe-智能运维工具",
        "overview": "文件管理，文件操作，软件包管理",
        "description": "文件管理，文件操作，软件包管理",
        "mcpType": "sse",
    }
    (mcp_server / "config.json").write_text(json.dumps(mcp_server_config, indent=2))

    # rag_mcp（SSE，config.json 格式）
    rag_mcp = mcp_center / "rag_mcp"
    rag_mcp.mkdir()
    rag_config = {
        "mcpServers": {
            "rag_mcp": {
                "headers": {},
                "autoApprove": [],
                "autoInstall": True,
                "timeout": 60,
                "url": "http://127.0.0.1:12311/sse",
            },
        },
        "name": "轻量化知识库",
        "overview": "轻量化知识库",
        "description": "轻量化知识库 RAG 服务",
        "mcpType": "sse",
    }
    (rag_mcp / "config.json").write_text(json.dumps(rag_config, indent=2))

    # 非 MCP 文件（应被 discovery 跳过）
    (mcp_center / "change.py").write_text("# not a server dir")
    (mcp_center / "mcp_to_app_config.toml").write_text("[app]")

    return mcp_center


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
def mock_config(mock_mcp_servers_dir, mock_mcp_center_dir, mock_state_directory):
    """创建模拟配置

    scan_paths 包含两个目录，对应真实 VM 的：
    - /opt/mcp-servers/servers       (RPM MCP)
    - /usr/lib/sysagent/mcp_center/mcp_config  (mcp_center MCP)
    """
    from witty_mcp_manager.config.config import ManagerConfig

    return ManagerConfig(
        scan_paths=[str(mock_mcp_servers_dir), str(mock_mcp_center_dir)],
        state_directory=str(mock_state_directory),
        runtime_directory=str(mock_state_directory / "runtime"),
        socket_path=str(mock_state_directory / "mcp-manager.sock"),
        command_allowlist=["uv", "python3", "python", "node", "npx"],
    )


# ============================================================================
# 真实 VM Fixtures - Admin MCP（私有格式）
# 来源: /usr/lib/sysagent/mcp_center/mcp_config/
# 注意：这些是 euler-copilot-framework 的私有格式，包含非标准字段
# ============================================================================


@pytest.fixture
def real_rag_mcp_config():
    """真实 rag_mcp 配置（Admin 私有 SSE 格式）

    来源: /usr/lib/sysagent/mcp_center/mcp_config/rag_mcp/config.json

    私有字段说明:
    - autoApprove: 映射到标准 alwaysAllow
    - autoInstall: 旧 Loader 专用，Witty 忽略
    - mcpType: 显式传输类型声明
    - overview: 简短概述
    """
    return {
        "mcpServers": {
            "rag_mcp": {
                "headers": {},
                "autoApprove": [],
                "autoInstall": True,
                "timeout": 60,
                "url": "http://127.0.0.1:12311/sse",
            },
        },
        "name": "轻量化知识库",
        "overview": "轻量化知识库",
        "description": (
            "基于 SQLite 的检索增强生成（RAG）知识库，提供知识库全生命周期管理。"
            "支持 TXT、DOCX、DOC、PDF 格式，采用 FTS5 全文检索与 sqlite-vec 向量检索"
            "的混合搜索策略，结合关键词与语义检索，提升检索准确性。"
        ),
        "mcpType": "sse",
    }


@pytest.fixture
def real_mcp_server_mcp_config():
    """真实 mcp_server_mcp 配置（Admin 私有 SSE 格式）

    来源: /usr/lib/sysagent/mcp_center/mcp_config/mcp_server_mcp/config.json
    """
    return {
        "mcpServers": {
            "mcp_server_mcp": {
                "headers": {},
                "autoApprove": [],
                "autoInstall": True,
                "timeout": 60,
                "url": "http://127.0.0.1:12555/sse",
            },
        },
        "name": "oe-智能运维工具",
        "overview": "文件管理，文件操作，软件包管理，系统信息查询，进程管理，网络修复，ssh修复",
        "description": "文件管理，文件操作，软件包管理，系统信息查询，进程管理，网络修复，ssh修复",
        "mcpType": "sse",
    }


# ============================================================================
# 真实 VM Fixtures - RPM MCP（标准格式）
# 来源: /opt/mcp-servers/servers/
# ============================================================================


@pytest.fixture
def real_git_mcp_config():
    """真实 git_mcp 配置（标准 STDIO 格式）

    来源: /opt/mcp-servers/servers/git_mcp/mcp_config.json
    使用标准 alwaysAllow 字段
    """
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
                    "git_diff_staged",
                    "git_diff",
                    "git_show",
                    "list_branches",
                ],
            },
        },
    }


@pytest.fixture
def real_git_mcp_rpm_yaml():
    """真实的 git_mcp mcp-rpm.yaml"""
    return {
        "name": "git-mcp",
        "summary": "MCP server for Git repository operations",
        "description": (
            "Provides MCP tools for interacting with Git repositories,\n"
            "including clone, pull, push and branch management.\n"
        ),
        "dependencies": {
            "system": ["python3", "uv", "python3-mcp", "jq"],
            "packages": ["git", "oegitext"],
        },
        "files": {
            "required": ["mcp_config.json", "src/git_mcp.py"],
            "optional": ["src/requirements.txt", "README.md"],
        },
    }


@pytest.fixture
def real_ccb_mcp_config():
    """真实的 ccb_mcp 配置（使用 python3 启动，含敏感参数）"""
    return {
        "mcpServers": {
            "ccbMcp": {
                "command": "python3",
                "args": [
                    "/opt/mcp-servers/servers/ccb_mcp/src/ccb_mcp.py",
                    "--HOME_DIR=${your_home_directory}",
                    "--SRV_HTTP_REPOSITORIES_HOST=eulermaker.compass-ci.openeuler.openatom.cn",
                    "--SRV_HTTP_REPOSITORIES_PORT=443",
                    "--SRV_HTTP_REPOSITORIES_PROTOCOL=https://",
                    "--GITEE_ID=${your_gitee_id}",
                    "--GITEE_PASSWORD=${your_gitee_password}",
                    "--ACCOUNT=${your_account}",
                    "--PASSWORD=${your_password}",
                ],
                "disabled": False,
            },
        },
    }


@pytest.fixture
def real_ccb_mcp_rpm_yaml():
    """真实的 ccb_mcp mcp-rpm.yaml"""
    return {
        "name": "ccb_mcp",
        "summary": "EulerMaker ccb MCP Server",
        "description": "MCP Server for interacting with EulerMaker using ccb commands.",
        "dependencies": {
            "system": ["python3", "uv", "python3-mcp"],
            "packages": ["ccb"],
        },
        "files": {
            "required": ["mcp_config.json", "src/ccb_mcp.py"],
            "optional": ["README.md"],
        },
    }


@pytest.fixture
def real_oedeploy_mcp_config():
    """真实的 oeDeploy_mcp 配置（upstream_key != 目录名）"""
    return {
        "mcpServers": {
            "mcp-oedp": {  # 注意：key 与目录名 oeDeploy_mcp 不同
                "command": "uv",
                "args": [
                    "--directory",
                    "/opt/mcp-servers/servers/oeDeploy_mcp/src",
                    "run",
                    "mcp-oedp.py",
                    "--model_url",
                    "https://api.deepseek.com",
                    "--api_key",
                    "<your key of deepseek api>",
                    "--model_name",
                    "deepseek-chat",
                ],
                "disabled": False,
                "timeout": 1800,
            },
        },
    }


@pytest.fixture
def real_oedeploy_mcp_rpm_yaml():
    """真实的 oeDeploy mcp-rpm.yaml"""
    return {
        "name": "oeDeploy",
        "summary": "MCP server for oeDeploy",
        "description": "Provides MCP tools for oeDeploy.\n",
        "dependencies": {
            "system": ["python3", "uv", "python3-mcp"],
            "packages": ["oedp"],
        },
        "files": {
            "required": ["mcp_config.json", "src/mcp-oedp.py"],
            "optional": ["src/requirements.txt", "src/pyproject.toml"],
        },
    }


@pytest.fixture
def real_cvekit_mcp_config():
    """真实的 cvekit_mcp 配置（含 env 字段）"""
    return {
        "mcpServers": {
            "cvekit_mcp": {
                "command": "uv",
                "env": {"LANG": "en_US.UTF-8"},
                "args": [
                    "--directory",
                    "/opt/mcp-servers/servers/cvekit_mcp/src",
                    "run",
                    "server.py",
                    "--llm-provider",
                    "deepseek",
                    "--gitee-token",
                    "",
                    "--api-key",
                    "",
                ],
                "disabled": False,
                "alwaysAllow": [],
                "description": "Gitee代码仓CVE补丁处理服务",
                "timeout": 600,
            },
        },
    }


@pytest.fixture
def real_cvekit_mcp_rpm_yaml():
    """真实的 cvekit mcp-rpm.yaml（含 python 依赖）"""
    return {
        "name": "cve_mcp",
        "summary": "OpenEuler CVE补丁处理服务",
        "description": "自动化处理OpenEuler CVE补丁的服务\n包括issue解析、补丁应用和PR创建\n",
        "dependencies": {
            "system": ["python3", "git", "patch", "oegitext"],
            "python": ["requests", "PyGithub", "curl_cffi"],
        },
        "files": {
            "required": ["src/server.py", "mcp_config.json"],
            "optional": ["src/requirements.txt"],
        },
    }


@pytest.fixture
def real_code_review_assistant_mcp_config():
    """真实 code_review_assistant_mcp 配置（使用非标准 autoApprove 字段）

    来源: /opt/mcp-servers/servers/code_review_assistant_mcp/mcp_config.json

    注意：这是 RPM MCP 中使用非标准 autoApprove 字段的特殊案例。
    虽然是 RPM MCP，但使用了私有格式的 autoApprove 字段。
    Normalizer 需要将 autoApprove 映射到 alwaysAllow。
    """
    return {
        "mcpServers": {
            "code_review_assistant": {
                "command": "uv",
                "args": [
                    "--directory",
                    "/opt/mcp-servers/servers/code_review_assistant_mcp/src",
                    "run",
                    "server.py",
                ],
                "disabled": False,
                "autoApprove": ["*"],  # 非标准字段，应映射到 alwaysAllow
            },
        },
    }


@pytest.fixture
def real_api_document_mcp_config():
    """真实的 api_document_mcp 配置"""
    return {
        "mcpServers": {
            "api_document_mcp": {
                "command": "uv",
                "args": [
                    "--directory",
                    "/opt/mcp-servers/servers/api_document_mcp/src",
                    "run",
                    "server.py",
                ],
                "disabled": False,
                "alwaysAllow": ["generate_docs"],
            },
        },
    }


@pytest.fixture
def real_network_manager_mcp_config():
    """真实的 network_manager_mcp 配置"""
    return {
        "mcpServers": {
            "network_manager_mcp": {
                "command": "uv",
                "args": [
                    "--directory",
                    "/opt/mcp-servers/servers/network_manager_mcp/src",
                    "run",
                    "server.py",
                ],
                "disabled": False,
                "alwaysAllow": [
                    "list_interfaces",
                    "get_interface_status",
                    "show_connections",
                ],
            },
        },
    }


@pytest.fixture
def mock_real_mcp_servers_dir(  # noqa: PLR0913
    tmp_path,
    real_git_mcp_config,
    real_git_mcp_rpm_yaml,
    real_ccb_mcp_config,
    real_ccb_mcp_rpm_yaml,
    real_oedeploy_mcp_config,
    real_oedeploy_mcp_rpm_yaml,
    real_cvekit_mcp_config,
    real_cvekit_mcp_rpm_yaml,
):
    """创建模拟的 /opt/mcp-servers/servers 目录（RPM MCP）"""
    import yaml

    servers_dir = tmp_path / "real_servers"
    servers_dir.mkdir()

    # git_mcp
    git_mcp = servers_dir / "git_mcp"
    git_mcp.mkdir()
    (git_mcp / "mcp_config.json").write_text(json.dumps(real_git_mcp_config, indent=2))
    (git_mcp / "mcp-rpm.yaml").write_text(yaml.dump(real_git_mcp_rpm_yaml))
    (git_mcp / "src").mkdir()
    (git_mcp / "src" / "git_mcp.py").write_text("# Git MCP Server")

    # Create ccb_mcp (upstream_key = ccbMcp)
    ccb_mcp = servers_dir / "ccb_mcp"
    ccb_mcp.mkdir()
    (ccb_mcp / "mcp_config.json").write_text(json.dumps(real_ccb_mcp_config, indent=2))
    (ccb_mcp / "mcp-rpm.yaml").write_text(yaml.dump(real_ccb_mcp_rpm_yaml))
    (ccb_mcp / "src").mkdir()
    (ccb_mcp / "src" / "ccb_mcp.py").write_text("# CCB MCP Server")

    # Create oeDeploy_mcp (upstream_key = mcp-oedp)
    oedp_mcp = servers_dir / "oeDeploy_mcp"
    oedp_mcp.mkdir()
    (oedp_mcp / "mcp_config.json").write_text(json.dumps(real_oedeploy_mcp_config, indent=2))
    (oedp_mcp / "mcp-rpm.yaml").write_text(yaml.dump(real_oedeploy_mcp_rpm_yaml))
    (oedp_mcp / "src").mkdir()
    (oedp_mcp / "src" / "mcp-oedp.py").write_text("# oeDeploy MCP Server")

    # cvekit_mcp (含 env 和 python 依赖)
    cvekit_mcp = servers_dir / "cvekit_mcp"
    cvekit_mcp.mkdir()
    (cvekit_mcp / "mcp_config.json").write_text(json.dumps(real_cvekit_mcp_config, indent=2))
    (cvekit_mcp / "mcp-rpm.yaml").write_text(yaml.dump(real_cvekit_mcp_rpm_yaml))
    (cvekit_mcp / "src").mkdir()
    (cvekit_mcp / "src" / "server.py").write_text("# CVEKit MCP Server")

    return servers_dir


@pytest.fixture
def mock_real_mcp_center_dir(
    tmp_path,
    real_mcp_server_mcp_config,
    real_rag_mcp_config,
):
    """创建模拟的 /usr/lib/sysagent/mcp_center/mcp_config 目录

    真实 VM 路径: /lib/sysagent/mcp_center/mcp_config/
    包含内容:
      mcp_server_mcp/config.json
      rag_mcp/config.json
      change.py                   (非 MCP，应被跳过)
      mcp_to_app_config.toml      (文件，应被跳过)
    """
    mcp_center = tmp_path / "real_mcp_config"
    mcp_center.mkdir()

    # mcp_server_mcp（SSE）
    mcp_server = mcp_center / "mcp_server_mcp"
    mcp_server.mkdir()
    (mcp_server / "config.json").write_text(json.dumps(real_mcp_server_mcp_config, indent=2))

    # rag_mcp（SSE）
    rag_mcp = mcp_center / "rag_mcp"
    rag_mcp.mkdir()
    (rag_mcp / "config.json").write_text(json.dumps(real_rag_mcp_config, indent=2))

    # 非 MCP 文件（真实 VM 中存在，应被跳过）
    (mcp_center / "change.py").write_text("# conversion script, not mcp")
    (mcp_center / "mcp_to_app_config.toml").write_text("[app]")

    return mcp_center


@pytest.fixture
def mock_real_config(mock_real_mcp_servers_dir, mock_real_mcp_center_dir, mock_state_directory):
    """创建使用真实 MCP 配置的 mock config

    scan_paths 对应真实 VM 的两个目录：
    - /opt/mcp-servers/servers                     (RPM MCP)
    - /usr/lib/sysagent/mcp_center/mcp_config      (mcp_center MCP)
    """
    from witty_mcp_manager.config.config import ManagerConfig

    return ManagerConfig(
        scan_paths=[str(mock_real_mcp_servers_dir), str(mock_real_mcp_center_dir)],
        state_directory=str(mock_state_directory),
        runtime_directory=str(mock_state_directory / "runtime"),
        socket_path=str(mock_state_directory / "mcp-manager.sock"),
        command_allowlist=["uv", "python3", "python", "node", "npx"],
    )


@pytest.fixture
def mock_server_record(tmp_path):
    """创建模拟的 ServerRecord 用于 CLI 测试"""
    from witty_mcp_manager.registry.models import (
        NormalizedConfig,
        ServerRecord,
        SourceType,
        StdioConfig,
        Timeouts,
        ToolPolicy,
        TransportType,
    )

    return ServerRecord(
        id="git_mcp",
        upstream_key="git-mcp",
        name="Git MCP",
        summary="Git repository operations",
        source=SourceType.RPM,
        transport=TransportType.STDIO,
        install_root=str(tmp_path / "git_mcp"),
        default_config=NormalizedConfig(
            transport=TransportType.STDIO,
            stdio=StdioConfig(
                command="uv",
                args=["--directory", str(tmp_path / "git_mcp" / "src"), "run", "git_mcp.py"],
            ),
            tool_policy=ToolPolicy(always_allow=["git_status"]),
            timeouts=Timeouts(),
        ),
        rpm_metadata={"name": "git-mcp"},
    )


# ============================================================================
# Admin MCP 目录 Fixtures（模拟 mcp_center 结构）
# ============================================================================


@pytest.fixture
def mock_admin_mcp_dir(tmp_path, real_rag_mcp_config, real_mcp_server_mcp_config):
    """创建模拟的 admin MCP 目录（基于 euler-copilot-framework mcp_center）

    目录结构：
    mcp_config/
    ├── rag_mcp/
    │   └── config.json
    ├── mcp_server_mcp/
    │   └── config.json
    └── mcp_to_app_config.toml
    """
    mcp_config_dir = tmp_path / "mcp_config"
    mcp_config_dir.mkdir()

    # Create rag_mcp directory for SSE-based knowledge base service
    rag_dir = mcp_config_dir / "rag_mcp"
    rag_dir.mkdir()
    (rag_dir / "config.json").write_text(json.dumps(real_rag_mcp_config, indent=2))

    # Create mcp_server_mcp directory for SSE-based ops tools
    mcp_server_dir = mcp_config_dir / "mcp_server_mcp"
    mcp_server_dir.mkdir()
    (mcp_server_dir / "config.json").write_text(json.dumps(real_mcp_server_mcp_config, indent=2))

    # Create mcp_to_app_config.toml (admin MCP specific file)
    (mcp_config_dir / "mcp_to_app_config.toml").write_text(
        """# Admin MCP to App Config
[mapping]
rag_mcp = "knowledge_base"
mcp_server_mcp = "system_ops"
""",
    )

    return mcp_config_dir


@pytest.fixture
def mock_sse_server_record(tmp_path):
    """创建模拟的 SSE ServerRecord 用于 admin MCP 测试"""
    from witty_mcp_manager.registry.models import (
        NormalizedConfig,
        ServerRecord,
        SourceType,
        SseConfig,
        Timeouts,
        ToolPolicy,
        TransportType,
    )

    return ServerRecord(
        id="rag_mcp",
        upstream_key="rag_mcp",
        name="轻量化知识库",
        summary="基于 SQLite 的 RAG 知识库服务",
        source=SourceType.ADMIN,
        transport=TransportType.SSE,
        install_root=str(tmp_path / "rag_mcp"),
        default_config=NormalizedConfig(
            transport=TransportType.SSE,
            sse=SseConfig(url="http://127.0.0.1:12311/sse", headers={}, timeout=60),
            tool_policy=ToolPolicy(always_allow=[]),
            timeouts=Timeouts(tool_call=60),
        ),
    )


@pytest.fixture
def mock_mcp_server_record(tmp_path):
    """创建模拟的 mcp_server_mcp ServerRecord"""
    from witty_mcp_manager.registry.models import (
        NormalizedConfig,
        ServerRecord,
        SourceType,
        SseConfig,
        Timeouts,
        ToolPolicy,
        TransportType,
    )

    return ServerRecord(
        id="mcp_server_mcp",
        upstream_key="mcp_server_mcp",
        name="oe-智能运维工具",
        summary="文件管理，软件包管理，系统信息查询，进程管理，网络修复",
        source=SourceType.ADMIN,
        transport=TransportType.SSE,
        install_root=str(tmp_path / "mcp_server_mcp"),
        default_config=NormalizedConfig(
            transport=TransportType.SSE,
            sse=SseConfig(url="http://127.0.0.1:12555/sse", headers={}, timeout=60),
            tool_policy=ToolPolicy(always_allow=[]),
            timeouts=Timeouts(tool_call=60),
        ),
    )
