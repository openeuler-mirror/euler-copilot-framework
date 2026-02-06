"""Witty MCP Manager 集成测试

测试类型：
1. MCP 服务器连接测试 - 验证能否连接到真实的 MCP 服务器
2. 工具调用测试 - 验证能否正确调用 MCP 工具
3. Witty MCP Manager 功能测试 - 验证核心管理功能

运行方式：
    # 在虚拟机上运行
    cd /path/to/witty_mcp_manager
    uv run pytest tests/integration/ -v

    # 仅运行连接测试
    uv run pytest tests/integration/test_mcp_servers.py::TestMCPConnection -v

    # 仅运行工具调用测试
    uv run pytest tests/integration/test_mcp_servers.py::TestMCPTools -v

环境要求：
    - 虚拟机: openeuler-2403sp3-mcp-dev
    - RPM MCP 已安装: /opt/mcp-servers/servers/
    - mcp_center MCP 服务已启动: mcp-server.service, rag.service
"""
# mypy: disable-error-code="no-untyped-def,misc,arg-type,call-arg,index,attr-defined,has-type,assignment,dict-item"

import asyncio
import json
import logging
import os
from contextlib import AsyncExitStack
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

# ============================================================================
# 配置和 Fixtures
# ============================================================================

# 是否在真实 VM 环境中运行
IN_VM = os.environ.get("WITTY_TEST_VM", "0") == "1" or Path("/opt/mcp-servers/servers").exists()

# RPM MCP 服务器配置
RPM_MCP_SERVERS = [
    {
        "name": "api_document_mcp",
        "command": ["uv", "--directory", "/opt/mcp-servers/servers/api_document_mcp/src", "run", "server.py"],
        "expected_tools": ["generate_docs"],
    },
    {
        "name": "code_review_assistant",
        "command": ["uv", "--directory", "/opt/mcp-servers/servers/code_review_assistant_mcp/src", "run", "server.py"],
        "expected_tools": ["analyze_code", "analyze_project"],
    },
    {
        "name": "code_search_mcp",
        "command": ["uv", "--directory", "/opt/mcp-servers/servers/code_search_mcp/src", "run", "server.py"],
        "expected_tools": ["search_code"],
    },
    {
        "name": "cvekit_mcp",
        "command": ["uv", "--directory", "/opt/mcp-servers/servers/cvekit_mcp/src", "run", "server.py"],
        "env": {"LANG": "en_US.UTF-8"},
        "expected_tools": ["parse_issue", "setup_env", "get_commits", "analyze_branches", "apply_patch", "create_pr"],
    },
    {
        "name": "git_mcp",
        "command": ["uv", "--directory", "/opt/mcp-servers/servers/git_mcp/src", "run", "git_mcp.py"],
        "expected_tools": ["git_status", "git_diff", "git_show", "list_branches"],
    },
    {
        "name": "network_manager_mcp",
        "command": ["uv", "--directory", "/opt/mcp-servers/servers/network_manager_mcp/src", "run", "server.py"],
        "expected_tools": ["list_interfaces", "get_interface_status", "show_connections"],
    },
    {
        "name": "mcp-oedp",
        "command": ["uv", "--directory", "/opt/mcp-servers/servers/oeDeploy_mcp/src", "run", "mcp-oedp.py"],
        "expected_tools": ["install_oedp", "remove_oedp"],
    },
    {
        "name": "oeGitExt_mcp",
        "command": [
            "uv",
            "--directory",
            "/opt/mcp-servers/servers/oeGitExt_mcp/src",
            "run",
            "oegitext_mcp.py",
            "--token=test_token",
        ],
        "expected_tools": ["get_my_openeuler_project", "get_my_openeuler_pr"],
    },
    {
        "name": "rpm-builder_mcp",
        "command": ["uv", "--directory", "/opt/mcp-servers/servers/rpm-builder_mcp/src", "run", "server.py"],
        "expected_tools": ["build_tar", "build_rpm"],
    },
    {
        "name": "ccbMcp",
        "command": ["python3", "/opt/mcp-servers/servers/ccb_mcp/src/ccb_mcp.py"],
        "expected_tools": ["select_projects", "select_builds", "build"],
    },
]

# SSE MCP 服务器配置
SSE_MCP_SERVERS = [
    {
        "name": "oe_cli_mcp",
        "url": "http://127.0.0.1:12555/sse",
        "expected_tools": ["cmd_executor_tool", "file_tool", "pkg_tool", "proc_tool", "sys_info_tool"],
    },
    {
        "name": "rag_mcp",
        "url": "http://127.0.0.1:12311/sse",
        "expected_tools": ["create_knowledge_base", "list_knowledge_bases", "search", "import_document"],
    },
]


@pytest.fixture
def skip_if_not_in_vm():
    """如果不在 VM 环境中则跳过测试"""
    if not IN_VM:
        pytest.skip("This test requires running in the VM environment")


# ============================================================================
# stdio 模式连接测试
# ============================================================================


class TestStdioMCPConnection:
    """stdio 模式 MCP 服务器连接测试"""

    @pytest.fixture
    def mcp_client_class(self):
        """获取 MCP 客户端类"""
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        return ClientSession, stdio_client

    @pytest.mark.skipif(not IN_VM, reason="Requires VM environment")
    @pytest.mark.asyncio
    @pytest.mark.parametrize("server", RPM_MCP_SERVERS, ids=[s["name"] for s in RPM_MCP_SERVERS])
    async def test_stdio_mcp_connection(self, server, mcp_client_class):
        """测试 stdio 模式 MCP 服务器连接"""
        client_session_cls, stdio_client = mcp_client_class

        command = server["command"]
        env = server.get("env", {})

        # 检查命令是否存在
        server_path = Path(command[2] if command[0] == "uv" else command[1]).parent
        if not server_path.exists():
            pytest.skip(f"Server path does not exist: {server_path}")

        exit_stack = AsyncExitStack()

        try:
            # 启动 stdio 客户端
            import os as os_module

            from mcp.client.stdio import StdioServerParameters

            full_env = os_module.environ.copy()
            full_env.update(env)

            server_params = StdioServerParameters(
                command=command[0],
                args=command[1:],
                env=full_env if env else None,
            )
            read, write = await exit_stack.enter_async_context(stdio_client(server_params))

            # 创建会话
            session = client_session_cls(read, write)
            await exit_stack.enter_async_context(session)

            # 初始化
            init_result = await asyncio.wait_for(session.initialize(), timeout=30)

            assert init_result.serverInfo is not None
            assert init_result.serverInfo.name is not None

            # 获取工具列表
            tools_result = await asyncio.wait_for(session.list_tools(), timeout=30)
            tools = tools_result.tools

            assert len(tools) > 0, f"Server {server['name']} has no tools"

            # 验证预期的工具存在
            tool_names = [t.name for t in tools]
            for expected_tool in server.get("expected_tools", []):
                assert expected_tool in tool_names, f"Expected tool '{expected_tool}' not found in {server['name']}"

        finally:
            await exit_stack.aclose()


# ============================================================================
# SSE 模式连接测试
# ============================================================================


class TestSSEMCPConnection:
    """SSE 模式 MCP 服务器连接测试"""

    @pytest.fixture
    def mcp_sse_client(self):
        """获取 SSE 客户端"""
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        return ClientSession, sse_client

    @pytest.mark.skipif(not IN_VM, reason="Requires VM environment")
    @pytest.mark.asyncio
    @pytest.mark.parametrize("server", SSE_MCP_SERVERS, ids=[s["name"] for s in SSE_MCP_SERVERS])
    async def test_sse_mcp_connection(self, server, mcp_sse_client):
        """测试 SSE 模式 MCP 服务器连接"""
        client_session_cls, sse_client = mcp_sse_client

        url = server["url"]

        # 检查服务是否运行
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url.replace("/sse", "/"))
                if response.status_code == 404:
                    pass  # 服务正常，只是没有 / 端点
                elif response.status_code >= 500:
                    pytest.skip(f"Server {server['name']} is not responding")
        except (httpx.ConnectError, httpx.ReadTimeout):
            pytest.skip(f"Server {server['name']} is not running at {url}")

        exit_stack = AsyncExitStack()

        try:
            # 连接 SSE 服务器
            client = sse_client(url=url, headers={})
            read, write = await exit_stack.enter_async_context(client)

            # 创建会话
            session = client_session_cls(read, write)
            await exit_stack.enter_async_context(session)

            # 初始化
            init_result = await asyncio.wait_for(session.initialize(), timeout=30)

            assert init_result.serverInfo is not None
            assert init_result.serverInfo.name is not None

            # 获取工具列表
            tools_result = await asyncio.wait_for(session.list_tools(), timeout=30)
            tools = tools_result.tools

            assert len(tools) > 0, f"Server {server['name']} has no tools"

            # 验证预期的工具存在
            tool_names = [t.name for t in tools]
            for expected_tool in server.get("expected_tools", []):
                assert expected_tool in tool_names, f"Expected tool '{expected_tool}' not found in {server['name']}"

        finally:
            await exit_stack.aclose()


# ============================================================================
# 工具调用测试
# ============================================================================


class TestMCPTools:
    """MCP 工具调用测试"""

    @pytest.mark.skipif(not IN_VM, reason="Requires VM environment")
    @pytest.mark.asyncio
    async def test_network_manager_list_interfaces(self):
        """测试 network_manager_mcp list_interfaces 工具"""
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        exit_stack = AsyncExitStack()

        try:
            from mcp.client.stdio import StdioServerParameters

            command = ["uv", "--directory", "/opt/mcp-servers/servers/network_manager_mcp/src", "run", "server.py"]
            server_params = StdioServerParameters(command=command[0], args=command[1:])
            read, write = await exit_stack.enter_async_context(stdio_client(server_params))

            session = ClientSession(read, write)
            await exit_stack.enter_async_context(session)
            await session.initialize()

            # 调用 list_interfaces
            result = await asyncio.wait_for(session.call_tool("list_interfaces", {}), timeout=30)

            assert result is not None
            assert result.content is not None
            assert len(result.content) > 0

        finally:
            await exit_stack.aclose()

    @pytest.mark.skipif(not IN_VM, reason="Requires VM environment")
    @pytest.mark.asyncio
    async def test_code_search_search_code(self):
        """测试 code_search_mcp search_code 工具"""
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        exit_stack = AsyncExitStack()

        try:
            from mcp.client.stdio import StdioServerParameters

            command = ["uv", "--directory", "/opt/mcp-servers/servers/code_search_mcp/src", "run", "server.py"]
            server_params = StdioServerParameters(command=command[0], args=command[1:])
            read, write = await exit_stack.enter_async_context(stdio_client(server_params))

            session = ClientSession(read, write)
            await exit_stack.enter_async_context(session)
            await session.initialize()

            # 调用 search_code
            result = await asyncio.wait_for(
                session.call_tool("search_code", {"search_term": "def ", "path": "/tmp"}), timeout=30
            )

            assert result is not None
            assert result.content is not None

        finally:
            await exit_stack.aclose()

    @pytest.mark.skipif(not IN_VM, reason="Requires VM environment")
    @pytest.mark.asyncio
    async def test_sse_sys_info_tool(self):
        """测试 oe_cli_mcp sys_info_tool 工具"""
        # 检查服务是否运行
        import httpx
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        url = "http://127.0.0.1:12555/sse"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.get(url.replace("/sse", "/"))
        except (httpx.ConnectError, httpx.ReadTimeout):
            pytest.skip("oe_cli_mcp service is not running")

        exit_stack = AsyncExitStack()

        try:
            client = sse_client(url=url, headers={})
            read, write = await exit_stack.enter_async_context(client)

            session = ClientSession(read, write)
            await exit_stack.enter_async_context(session)
            await session.initialize()

            # 调用 sys_info_tool
            result = await asyncio.wait_for(session.call_tool("sys_info_tool", {"info_types": ["os_info"]}), timeout=30)

            assert result is not None
            assert result.content is not None
            assert len(result.content) > 0

        finally:
            await exit_stack.aclose()

    @pytest.mark.skipif(not IN_VM, reason="Requires VM environment")
    @pytest.mark.asyncio
    async def test_sse_rag_list_knowledge_bases(self):
        """测试 rag_mcp list_knowledge_bases 工具"""
        # 检查服务是否运行
        import httpx
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        url = "http://127.0.0.1:12311/sse"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.get(url.replace("/sse", "/"))
        except (httpx.ConnectError, httpx.ReadTimeout):
            pytest.skip("rag_mcp service is not running")

        exit_stack = AsyncExitStack()

        try:
            client = sse_client(url=url, headers={})
            read, write = await exit_stack.enter_async_context(client)

            session = ClientSession(read, write)
            await exit_stack.enter_async_context(session)
            await session.initialize()

            # 调用 list_knowledge_bases
            result = await asyncio.wait_for(session.call_tool("list_knowledge_bases", {}), timeout=30)

            assert result is not None
            assert result.content is not None

        finally:
            await exit_stack.aclose()


# ============================================================================
# 测试数据收集
# ============================================================================


class TestDataCollection:
    """测试数据收集 - 收集真实的 MCP 配置和工具信息"""

    @pytest.mark.skipif(not IN_VM, reason="Requires VM environment")
    @pytest.mark.asyncio
    async def test_collect_stdio_mcp_data(self, tmp_path):
        """收集 stdio MCP 服务器数据"""
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        results = {}

        for server in RPM_MCP_SERVERS:
            server_name = server["name"]
            command = server["command"]
            env = server.get("env", {})

            try:
                exit_stack = AsyncExitStack()

                import os as os_module

                from mcp.client.stdio import StdioServerParameters

                full_env = os_module.environ.copy()
                full_env.update(env)

                server_params = StdioServerParameters(
                    command=command[0],
                    args=command[1:],
                    env=full_env if env else None,
                )
                read, write = await exit_stack.enter_async_context(stdio_client(server_params))

                session = ClientSession(read, write)
                await exit_stack.enter_async_context(session)

                init_result = await asyncio.wait_for(session.initialize(), timeout=30)
                tools_result = await asyncio.wait_for(session.list_tools(), timeout=30)

                results[server_name] = {
                    "status": "success",
                    "server_info": {
                        "name": init_result.serverInfo.name,
                        "version": init_result.serverInfo.version,
                    },
                    "tools": [
                        {
                            "name": t.name,
                            "description": str(t.description)[:200] if t.description else "",
                            "input_schema": t.inputSchema,
                        }
                        for t in tools_result.tools
                    ],
                }

                await exit_stack.aclose()

            except (ConnectionError, TimeoutError, OSError) as e:
                results[server_name] = {
                    "status": "failed",
                    "error": str(e),
                }

        # 保存结果
        output_file = tmp_path / "stdio_mcp_data.json"
        output_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))

        # 验证至少有一个成功
        success_count = sum(1 for r in results.values() if r["status"] == "success")
        assert success_count > 0, "All stdio MCP connections failed"

        logger.info("Stdio MCP data saved to: %s", output_file)
        logger.info("Success: %d/%d", success_count, len(results))

    @pytest.mark.skipif(not IN_VM, reason="Requires VM environment")
    @pytest.mark.asyncio
    async def test_collect_sse_mcp_data(self, tmp_path):
        """收集 SSE MCP 服务器数据"""
        import httpx
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        results = {}

        for server in SSE_MCP_SERVERS:
            server_name = server["name"]
            url = server["url"]

            try:
                # 检查服务是否运行
                async with httpx.AsyncClient(timeout=5.0) as http_client:
                    try:
                        await http_client.get(url.replace("/sse", "/"))
                    except (httpx.ConnectError, httpx.ReadTimeout):
                        results[server_name] = {
                            "status": "skipped",
                            "error": "Service not running",
                        }
                        continue

                exit_stack = AsyncExitStack()

                client = sse_client(url=url, headers={})
                read, write = await exit_stack.enter_async_context(client)

                session = ClientSession(read, write)
                await exit_stack.enter_async_context(session)

                init_result = await asyncio.wait_for(session.initialize(), timeout=30)
                tools_result = await asyncio.wait_for(session.list_tools(), timeout=30)

                results[server_name] = {
                    "status": "success",
                    "url": url,
                    "server_info": {
                        "name": init_result.serverInfo.name,
                        "version": init_result.serverInfo.version,
                    },
                    "tools": [
                        {
                            "name": t.name,
                            "description": str(t.description)[:200] if t.description else "",
                            "input_schema": t.inputSchema,
                        }
                        for t in tools_result.tools
                    ],
                }

                await exit_stack.aclose()

            except (ConnectionError, TimeoutError, OSError) as e:
                results[server_name] = {
                    "status": "failed",
                    "error": str(e),
                }

        # 保存结果
        output_file = tmp_path / "sse_mcp_data.json"
        output_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))

        # 验证至少有一个成功
        success_count = sum(1 for r in results.values() if r["status"] == "success")
        assert success_count > 0 or all(r["status"] == "skipped" for r in results.values()), (
            "All SSE MCP connections failed (not just skipped)"
        )

        logger.info("SSE MCP data saved to: %s", output_file)
        logger.info("Success: %d/%d", success_count, len(results))
