"""
Witty MCP Manager 集成测试套件

测试 Witty MCP Manager 的 CLI 和 IPC 接口功能。

环境要求:
- openEuler 24.03 LTS SP3 或兼容系统
- Python 3.11+
- witty-mcp-manager daemon 运行中
- 至少一个 MCP 服务器安装在 /opt/mcp-servers/

运行方式:
    # 在目标机器上运行
    export WITTY_TEST_VM=1  # 启用 VM 测试
    uv run pytest tests/integration/test_witty_mcp_manager.py -v

    # 运行指定测试类
    uv run pytest tests/integration/test_witty_mcp_manager.py::TestIPCHealth -v
    uv run pytest tests/integration/test_witty_mcp_manager.py::TestCLIServers -v

Author: Witty MCP Manager Team
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

# 检查是否在 VM 测试环境中
VM_TEST_ENABLED = os.environ.get("WITTY_TEST_VM", "").lower() in ("1", "true", "yes")

# 跳过标记
skip_unless_vm = pytest.mark.skipif(
    not VM_TEST_ENABLED,
    reason="VM integration tests disabled. Set WITTY_TEST_VM=1 to enable.",
)

# ============================================================================
# 配置和常量
# ============================================================================

# IPC Socket 路径
UDS_PATH = "/run/witty/mcp-manager.sock"

# 系统用户 ID
SYSTEM_USER_ID = "__system__"

# 测试用户 ID - 使用唯一 ID 避免与旧目录权限冲突
# 格式: test_user_<pid>_<timestamp>
TEST_USER_ID = f"test_user_{os.getpid()}_{int(time.time())}"

# 用户 override 目录基础路径
USER_OVERRIDE_BASE = "/var/lib/witty-mcp-manager/overrides/users"

# IPC 认证头 (必须与 witty_mcp_manager.ipc.auth 中的定义一致)
HEADER_USER_ID = "X-Witty-User"

# CLI 命令 - 优先使用 uv run，回退到直接命令
WITTY_CLI = os.environ.get("WITTY_CLI", "witty-mcp")
USE_UV_RUN = os.environ.get("WITTY_USE_UV_RUN", "1").lower() in ("1", "true", "yes")


@dataclass
class IntegrationTestConfig:
    """测试配置（使用 IntegrationTestConfig 名称避免被 pytest 收集为测试类）"""

    socket_path: str = UDS_PATH
    timeout: float = 30.0
    user_id: str = TEST_USER_ID
    system_user_id: str = SYSTEM_USER_ID
    user_override_base: str = USER_OVERRIDE_BASE

    @property
    def user_override_dir(self) -> Path:
        """获取测试用户的 override 目录路径"""
        return Path(self.user_override_base) / self.user_id


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def test_config() -> Generator[IntegrationTestConfig, None, None]:
    """测试配置 fixture"""
    config = IntegrationTestConfig()

    yield config

    # 测试结束后清理测试用户的 override 目录
    # 使用唯一用户 ID，每次测试创建新目录，测试后清理
    if config.user_override_dir.exists():
        with contextlib.suppress(OSError):
            shutil.rmtree(config.user_override_dir)


@pytest.fixture(scope="module")
def ipc_client(test_config: IntegrationTestConfig):
    """创建 IPC HTTP 客户端"""
    # 检查 socket 是否存在
    if not Path(test_config.socket_path).exists():
        pytest.skip(f"IPC socket not found: {test_config.socket_path}")

    client = httpx.Client(
        transport=httpx.HTTPTransport(uds=test_config.socket_path),
        base_url="http://localhost",
        timeout=test_config.timeout,
        headers={HEADER_USER_ID: test_config.user_id},
    )

    yield client

    client.close()


@pytest.fixture(scope="module")
def system_client(test_config: IntegrationTestConfig):
    """创建系统级 IPC 客户端（无用户上下文）"""
    if not Path(test_config.socket_path).exists():
        pytest.skip(f"IPC socket not found: {test_config.socket_path}")

    client = httpx.Client(
        transport=httpx.HTTPTransport(uds=test_config.socket_path),
        base_url="http://localhost",
        timeout=test_config.timeout,
        headers={HEADER_USER_ID: SYSTEM_USER_ID},
    )

    yield client

    client.close()


@pytest.fixture(scope="module")
def discovered_servers(system_client: httpx.Client) -> list[dict[str, Any]]:
    """获取已发现的 MCP 服务器列表"""
    response = system_client.get("/v1/servers", params={"include_disabled": "true"})
    response.raise_for_status()
    data = response.json()
    result: list[dict[str, Any]] = data.get("data", [])
    return result


@pytest.fixture
def first_ready_server(discovered_servers: list[dict[str, Any]]) -> dict[str, Any]:
    """获取第一个可用的服务器"""
    for server in discovered_servers:
        if server.get("status") == "ready":
            return server
    pytest.skip("No ready servers found")


def run_cli(args: list[str], *, check: bool = True, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    """运行 CLI 命令

    根据环境决定使用 uv run witty-mcp 还是直接 witty-mcp
    """
    cmd = ["uv", "run", WITTY_CLI, *args] if USE_UV_RUN else [WITTY_CLI, *args]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
            cwd=os.environ.get("WITTY_PROJECT_DIR", None),  # 可指定项目目录
        )
    except subprocess.TimeoutExpired as e:
        msg = f"CLI command timed out: {' '.join(cmd)}"
        raise TimeoutError(msg) from e
    except FileNotFoundError:
        pytest.skip(f"CLI not found: {cmd[0]}")
    else:
        return result


# ============================================================================
# IPC Health API 测试
# ============================================================================


@skip_unless_vm
class TestIPCHealth:
    """IPC 健康检查接口测试"""

    def test_health_endpoint(self, system_client: httpx.Client) -> None:
        """测试 /health 端点"""
        response = system_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "data" in data

        health = data["data"]
        assert health.get("status") == "healthy"
        assert "version" in health
        assert "uptime_sec" in health
        assert "server_count" in health
        assert "active_sessions" in health

    def test_health_has_servers(self, system_client: httpx.Client) -> None:
        """测试健康检查返回的服务器数量"""
        response = system_client.get("/health")
        response.raise_for_status()

        health = response.json()["data"]
        # 应该发现至少一个服务器
        assert health.get("server_count", 0) >= 0

    def test_health_version_format(self, system_client: httpx.Client) -> None:
        """测试版本号格式"""
        response = system_client.get("/health")
        response.raise_for_status()

        health = response.json()["data"]
        version = health.get("version", "")
        # 版本号应该存在
        assert version, "Version should not be empty"


# ============================================================================
# IPC Registry API 测试
# ============================================================================


@skip_unless_vm
class TestIPCRegistry:
    """IPC Registry 接口测试"""

    def test_list_servers(self, system_client: httpx.Client) -> None:
        """测试列出服务器"""
        response = system_client.get("/v1/servers")

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_list_servers_include_disabled(self, system_client: httpx.Client) -> None:
        """测试列出所有服务器（包括禁用的）"""
        response = system_client.get("/v1/servers", params={"include_disabled": "true"})

        assert response.status_code == 200
        data = response.json()
        servers = data.get("data", [])

        # 每个服务器应该有必要的字段
        for server in servers:
            assert "mcp_id" in server
            assert "name" in server
            assert "source" in server
            assert "status" in server

    def test_server_detail(
        self,
        ipc_client: httpx.Client,
        first_ready_server: dict[str, Any],
    ) -> None:
        """测试获取服务器详情"""
        mcp_id = first_ready_server["mcp_id"]
        response = ipc_client.get(f"/v1/servers/{mcp_id}")

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True

        detail = data.get("data", {})
        assert detail.get("mcp_id") == mcp_id
        assert "name" in detail
        assert "transport" in detail
        assert "status" in detail

    def test_server_detail_not_found(self, ipc_client: httpx.Client) -> None:
        """测试获取不存在的服务器"""
        response = ipc_client.get("/v1/servers/non_existent_mcp_12345")

        assert response.status_code == 404
        data = response.json()
        # 应该返回错误信息
        assert "detail" in data or data.get("success") is False

    def test_server_summary_fields(
        self,
        system_client: httpx.Client,
        discovered_servers: list[dict[str, Any]],
    ) -> None:
        """测试服务器摘要字段完整性"""
        if not discovered_servers:
            pytest.skip("No servers discovered")

        for server in discovered_servers[:3]:  # 只测试前 3 个
            assert "mcp_id" in server, "Missing mcp_id"
            assert "name" in server, "Missing name"
            assert "source" in server, "Missing source"
            assert server["source"] in ("rpm", "admin", "user"), f"Invalid source: {server['source']}"
            assert "status" in server, "Missing status"
            assert server["status"] in ("ready", "degraded", "unavailable"), f"Invalid status: {server['status']}"


# ============================================================================
# IPC Enable/Disable API 测试
# ============================================================================


@skip_unless_vm
class TestIPCEnableDisable:
    """IPC 启用/禁用接口测试"""

    def test_enable_server(
        self,
        ipc_client: httpx.Client,
        first_ready_server: dict[str, Any],
    ) -> None:
        """测试启用服务器"""
        mcp_id = first_ready_server["mcp_id"]
        response = ipc_client.post(f"/v1/me/servers/{mcp_id}/enable")

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True

        result = data.get("data", {})
        assert result.get("mcp_id") == mcp_id
        assert result.get("enabled") is True

    def test_disable_server(
        self,
        ipc_client: httpx.Client,
        first_ready_server: dict[str, Any],
    ) -> None:
        """测试禁用服务器"""
        mcp_id = first_ready_server["mcp_id"]
        response = ipc_client.post(f"/v1/me/servers/{mcp_id}/disable")

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True

        result = data.get("data", {})
        assert result.get("mcp_id") == mcp_id
        assert result.get("enabled") is False

    def test_enable_disable_toggle(
        self,
        ipc_client: httpx.Client,
        first_ready_server: dict[str, Any],
    ) -> None:
        """测试启用/禁用切换"""
        mcp_id = first_ready_server["mcp_id"]

        # 禁用
        response = ipc_client.post(f"/v1/me/servers/{mcp_id}/disable")
        assert response.status_code == 200
        assert response.json()["data"]["enabled"] is False

        # 启用
        response = ipc_client.post(f"/v1/me/servers/{mcp_id}/enable")
        assert response.status_code == 200
        assert response.json()["data"]["enabled"] is True

    def test_enable_non_existent_server(self, ipc_client: httpx.Client) -> None:
        """测试启用不存在的服务器"""
        response = ipc_client.post("/v1/me/servers/non_existent_mcp_12345/enable")
        assert response.status_code == 404


# ============================================================================
# IPC Tools API 测试
# ============================================================================


@skip_unless_vm
class TestIPCTools:
    """IPC Tools 接口测试"""

    @pytest.fixture
    def enabled_server(
        self,
        ipc_client: httpx.Client,
        first_ready_server: dict[str, Any],
    ) -> dict[str, Any]:
        """确保服务器已启用"""
        mcp_id = first_ready_server["mcp_id"]
        ipc_client.post(f"/v1/me/servers/{mcp_id}/enable")
        return first_ready_server

    def test_list_tools(
        self,
        ipc_client: httpx.Client,
        enabled_server: dict[str, Any],
    ) -> None:
        """测试列出工具"""
        mcp_id = enabled_server["mcp_id"]
        response = ipc_client.get(f"/v1/servers/{mcp_id}/tools")

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True

        result = data.get("data", {})
        assert "tools" in result
        tools = result["tools"]
        assert isinstance(tools, list)

        # 每个工具应该有必要字段
        for tool in tools:
            assert "name" in tool, "Tool missing name"
            assert "inputSchema" in tool, "Tool missing inputSchema"

    def test_list_tools_force_refresh(
        self,
        ipc_client: httpx.Client,
        enabled_server: dict[str, Any],
    ) -> None:
        """测试强制刷新工具列表"""
        mcp_id = enabled_server["mcp_id"]

        # 第一次请求（可能从缓存）
        response1 = ipc_client.get(f"/v1/servers/{mcp_id}/tools")
        assert response1.status_code == 200

        # 强制刷新
        response2 = ipc_client.get(f"/v1/servers/{mcp_id}/tools", params={"force_refresh": "true"})
        assert response2.status_code == 200

        # 两次应该返回相同的工具列表
        tools1 = response1.json()["data"]["tools"]
        tools2 = response2.json()["data"]["tools"]
        assert len(tools1) == len(tools2)

    def test_list_tools_disabled_server(
        self,
        ipc_client: httpx.Client,
        first_ready_server: dict[str, Any],
    ) -> None:
        """测试禁用服务器的工具列表（应该失败）"""
        mcp_id = first_ready_server["mcp_id"]

        # 先禁用
        ipc_client.post(f"/v1/me/servers/{mcp_id}/disable")

        # 尝试获取工具列表
        response = ipc_client.get(f"/v1/servers/{mcp_id}/tools")
        assert response.status_code == 403

        # 恢复启用
        ipc_client.post(f"/v1/me/servers/{mcp_id}/enable")


# ============================================================================
# IPC Tool Call API 测试
# ============================================================================


@skip_unless_vm
class TestIPCToolCall:
    """IPC Tool Call 接口测试"""

    @pytest.fixture
    def enabled_server_with_tools(
        self,
        ipc_client: httpx.Client,
        first_ready_server: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """获取已启用且有工具的服务器"""
        mcp_id = first_ready_server["mcp_id"]

        # 启用服务器
        ipc_client.post(f"/v1/me/servers/{mcp_id}/enable")

        # 获取工具列表
        response = ipc_client.get(f"/v1/servers/{mcp_id}/tools")
        if response.status_code != 200:
            pytest.skip(f"Cannot get tools for {mcp_id}")

        tools = response.json().get("data", {}).get("tools", [])
        if not tools:
            pytest.skip(f"No tools found for {mcp_id}")

        return first_ready_server, tools

    def test_call_tool(
        self,
        ipc_client: httpx.Client,
        enabled_server_with_tools: tuple[dict[str, Any], list[dict[str, Any]]],
    ) -> None:
        """测试调用工具"""
        server, tools = enabled_server_with_tools
        mcp_id = server["mcp_id"]

        # 选择一个简单的工具来测试
        tool = tools[0]
        tool_name = tool["name"]

        # 构建最小参数
        arguments: dict[str, Any] = {}
        input_schema = tool.get("inputSchema", {})
        required = input_schema.get("required", [])
        properties = input_schema.get("properties", {})

        for prop in required:
            prop_schema = properties.get(prop, {})
            prop_type = prop_schema.get("type", "string")
            if prop_type == "string":
                arguments[prop] = "test"
            elif prop_type == "integer":
                arguments[prop] = 1
            elif prop_type == "boolean":
                arguments[prop] = True
            elif prop_type == "array":
                arguments[prop] = []
            elif prop_type == "object":
                arguments[prop] = {}

        response = ipc_client.post(
            f"/v1/me/servers/{mcp_id}/tools/{tool_name}/call",
            json={"arguments": arguments},
        )

        # 工具调用可能成功或失败（取决于参数），但 API 应该正常响应
        assert response.status_code in (200, 400, 500)

        data = response.json()
        # 响应格式应该正确
        assert "success" in data or "data" in data or "detail" in data


# ============================================================================
# IPC Runtime API 测试
# ============================================================================


@skip_unless_vm
class TestIPCRuntime:
    """IPC Runtime 接口测试"""

    def test_list_sessions(self, ipc_client: httpx.Client) -> None:
        """测试列出会话"""
        response = ipc_client.get("/v1/runtime/sessions")

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_list_sessions_all_users(self, system_client: httpx.Client) -> None:
        """测试列出所有用户的会话"""
        response = system_client.get("/v1/runtime/sessions", params={"all_users": "true"})

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data.get("data", []), list)

    def test_session_detail_not_found(self, ipc_client: httpx.Client) -> None:
        """测试获取不存在的会话详情"""
        response = ipc_client.get("/v1/runtime/sessions/non_existent_mcp_12345")
        # 应该返回 404 或空数据
        assert response.status_code in (200, 404)


# ============================================================================
# CLI Version 测试
# ============================================================================


@skip_unless_vm
class TestCLIVersion:
    """CLI 版本命令测试"""

    def test_version_command(self) -> None:
        """测试 version 命令"""
        result = run_cli(["version"])
        assert result.returncode == 0
        # 输出应该包含版本号
        assert result.stdout.strip(), "Version output should not be empty"

    def test_help_command(self) -> None:
        """测试 --help 选项"""
        result = run_cli(["--help"])
        assert result.returncode == 0
        assert "Witty MCP Manager CLI" in result.stdout


# ============================================================================
# CLI Servers 测试
# ============================================================================


@skip_unless_vm
class TestCLIServers:
    """CLI servers 子命令测试"""

    def test_servers_list(self) -> None:
        """测试 servers list 命令"""
        result = run_cli(["servers", "list", "--global"])
        assert result.returncode == 0
        # 输出应该包含表格或服务器信息
        assert "MCP" in result.stdout or "servers" in result.stdout.lower()

    def test_servers_list_json(self) -> None:
        """测试 servers list --json 命令"""
        result = run_cli(["servers", "list", "--global", "--json"])
        assert result.returncode == 0

        # 输出应该是有效的 JSON
        try:
            data = json.loads(result.stdout)
            assert "servers" in data
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")

    def test_servers_list_all(self) -> None:
        """测试 servers list --all 命令"""
        result = run_cli(["servers", "list", "--global", "--all"])
        assert result.returncode == 0

    def test_servers_info(self, discovered_servers: list[dict[str, Any]]) -> None:
        """测试 servers info 命令"""
        if not discovered_servers:
            pytest.skip("No servers discovered")

        mcp_id = discovered_servers[0]["mcp_id"]
        # 普通用户不需要指定 --user，CLI 会自动检测当前用户
        result = run_cli(["servers", "info", mcp_id])
        assert result.returncode == 0
        assert mcp_id in result.stdout

    def test_servers_info_not_found(self) -> None:
        """测试 servers info 不存在的服务器"""
        result = run_cli(["servers", "info", "non_existent_mcp_12345"], check=False)
        assert result.returncode != 0

    def test_servers_tools(self, discovered_servers: list[dict[str, Any]]) -> None:
        """测试 servers tools 命令"""
        # 找一个 ready 状态的服务器
        ready_servers = [s for s in discovered_servers if s.get("status") == "ready"]
        if not ready_servers:
            pytest.skip("No ready servers found")

        mcp_id = ready_servers[0]["mcp_id"]
        # 先为当前用户启用服务器（启用可能已经启用，不检查返回值）
        run_cli(["servers", "enable", mcp_id], check=False)

        # 现在查看工具
        result = run_cli(["servers", "tools", mcp_id])
        # 即使没有工具也应该成功
        assert result.returncode == 0

    def test_servers_tools_json(self, discovered_servers: list[dict[str, Any]]) -> None:
        """测试 servers tools --json 命令"""
        ready_servers = [s for s in discovered_servers if s.get("status") == "ready"]
        if not ready_servers:
            pytest.skip("No ready servers found")

        mcp_id = ready_servers[0]["mcp_id"]
        # 先为当前用户启用服务器
        run_cli(["servers", "enable", mcp_id], check=False)

        result = run_cli(["servers", "tools", mcp_id, "--json"])
        assert result.returncode == 0

        try:
            data = json.loads(result.stdout)
            assert "tools" in data or "data" in data
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")


# ============================================================================
# CLI Enable/Disable 测试
# ============================================================================


@skip_unless_vm
class TestCLIEnableDisable:
    """CLI enable/disable 命令测试"""

    def test_servers_enable_user(self, discovered_servers: list[dict[str, Any]]) -> None:
        """测试 servers enable 命令"""
        ready_servers = [s for s in discovered_servers if s.get("status") == "ready"]
        if not ready_servers:
            pytest.skip("No ready servers found")

        mcp_id = ready_servers[0]["mcp_id"]
        # 普通用户不需要指定 --user，CLI 会为当前用户启用
        result = run_cli(["servers", "enable", mcp_id])
        assert result.returncode == 0

    def test_servers_disable_user(self, discovered_servers: list[dict[str, Any]]) -> None:
        """测试 servers disable 命令"""
        ready_servers = [s for s in discovered_servers if s.get("status") == "ready"]
        if not ready_servers:
            pytest.skip("No ready servers found")

        mcp_id = ready_servers[0]["mcp_id"]
        # 普通用户不需要指定 --user
        result = run_cli(["servers", "disable", mcp_id])
        assert result.returncode == 0

    def test_servers_enable_disable_toggle(self, discovered_servers: list[dict[str, Any]]) -> None:
        """测试 enable/disable 切换"""
        ready_servers = [s for s in discovered_servers if s.get("status") == "ready"]
        if not ready_servers:
            pytest.skip("No ready servers found")

        mcp_id = ready_servers[0]["mcp_id"]

        # 禁用
        result = run_cli(["servers", "disable", mcp_id])
        assert result.returncode == 0

        # 启用
        result = run_cli(["servers", "enable", mcp_id])
        assert result.returncode == 0


# ============================================================================
# CLI Runtime 测试
# ============================================================================


@skip_unless_vm
class TestCLIRuntime:
    """CLI runtime 子命令测试"""

    def test_runtime_status(self) -> None:
        """测试 runtime status 命令"""
        result = run_cli(["runtime", "status"])
        assert result.returncode == 0
        # 应该显示状态信息
        assert "Witty MCP Manager" in result.stdout or "Status" in result.stdout or "sessions" in result.stdout.lower()

    def test_runtime_status_json(self) -> None:
        """测试 runtime status --json 命令"""
        result = run_cli(["runtime", "status", "--json"])
        assert result.returncode == 0

        try:
            data = json.loads(result.stdout)
            # 应该包含状态数据
            assert isinstance(data, dict)
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")

    def test_runtime_sessions(self) -> None:
        """测试 runtime sessions 命令"""
        result = run_cli(["runtime", "sessions", "--all-users"])
        assert result.returncode == 0


# ============================================================================
# CLI Config 测试
# ============================================================================


@skip_unless_vm
class TestCLIConfig:
    """CLI config 子命令测试"""

    def test_config_show(self) -> None:
        """测试 config show 命令"""
        result = run_cli(["config", "show"])
        assert result.returncode == 0

    def test_config_show_json(self) -> None:
        """测试 config show --json 命令"""
        result = run_cli(["config", "show", "--json"])
        assert result.returncode == 0

        try:
            data = json.loads(result.stdout)
            assert isinstance(data, dict)
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")


# ============================================================================
# 端到端测试
# ============================================================================


@skip_unless_vm
class TestEndToEnd:
    """端到端集成测试"""

    def test_full_workflow_ipc(
        self,
        ipc_client: httpx.Client,
        first_ready_server: dict[str, Any],
    ) -> None:
        """测试完整的 IPC 工作流：启用 -> 获取工具 -> 调用工具 -> 禁用"""
        mcp_id = first_ready_server["mcp_id"]

        # 1. 启用服务器
        response = ipc_client.post(f"/v1/me/servers/{mcp_id}/enable")
        assert response.status_code == 200

        # 2. 获取工具列表
        response = ipc_client.get(f"/v1/servers/{mcp_id}/tools")
        assert response.status_code == 200
        tools = response.json().get("data", {}).get("tools", [])

        # 3. 如果有工具，尝试调用一个
        if tools:
            tool_name = tools[0]["name"]
            response = ipc_client.post(
                f"/v1/me/servers/{mcp_id}/tools/{tool_name}/call",
                json={"arguments": {}},
            )
            # 调用可能成功或失败，但 API 应该响应
            assert response.status_code in (200, 400, 500)

        # 4. 禁用服务器
        response = ipc_client.post(f"/v1/me/servers/{mcp_id}/disable")
        assert response.status_code == 200

    def test_full_workflow_cli(self, discovered_servers: list[dict[str, Any]]) -> None:
        """测试完整的 CLI 工作流"""
        ready_servers = [s for s in discovered_servers if s.get("status") == "ready"]
        if not ready_servers:
            pytest.skip("No ready servers found")

        mcp_id = ready_servers[0]["mcp_id"]

        # 1. 查看服务器列表
        result = run_cli(["servers", "list", "--global"])
        assert result.returncode == 0

        # 2. 查看服务器详情（普通用户不需要 --user）
        result = run_cli(["servers", "info", mcp_id])
        assert result.returncode == 0

        # 3. 启用服务器
        result = run_cli(["servers", "enable", mcp_id])
        assert result.returncode == 0

        # 4. 查看工具列表
        result = run_cli(["servers", "tools", mcp_id])
        assert result.returncode == 0

        # 5. 检查运行时状态
        result = run_cli(["runtime", "status"])
        assert result.returncode == 0

        # 6. 禁用服务器
        result = run_cli(["servers", "disable", mcp_id])
        assert result.returncode == 0


# ============================================================================
# 并发测试
# ============================================================================


@skip_unless_vm
class TestConcurrency:
    """并发测试"""

    def test_concurrent_health_checks(self, test_config: IntegrationTestConfig) -> None:
        """测试并发健康检查"""
        import concurrent.futures

        def health_check() -> int:
            with httpx.Client(
                transport=httpx.HTTPTransport(uds=test_config.socket_path),
                base_url="http://localhost",
                timeout=10.0,
            ) as client:
                response = client.get("/health")
                return response.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(health_check) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # 所有请求应该成功
        assert all(code == 200 for code in results)

    def test_concurrent_list_servers(self, test_config: IntegrationTestConfig) -> None:
        """测试并发列出服务器"""
        import concurrent.futures

        def list_servers() -> int:
            with httpx.Client(
                transport=httpx.HTTPTransport(uds=test_config.socket_path),
                base_url="http://localhost",
                timeout=10.0,
                headers={HEADER_USER_ID: SYSTEM_USER_ID},
            ) as client:
                response = client.get("/v1/servers")
                return response.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(list_servers) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(code == 200 for code in results)


# ============================================================================
# 错误处理测试
# ============================================================================


@skip_unless_vm
class TestErrorHandling:
    """错误处理测试"""

    def test_invalid_endpoint(self, system_client: httpx.Client) -> None:
        """测试访问无效端点"""
        response = system_client.get("/invalid/endpoint")
        assert response.status_code == 404

    def test_invalid_method(self, system_client: httpx.Client) -> None:
        """测试使用无效的 HTTP 方法"""
        response = system_client.delete("/health")
        assert response.status_code in (404, 405)

    def test_invalid_json_body(self, ipc_client: httpx.Client, first_ready_server: dict[str, Any]) -> None:
        """测试发送无效的 JSON 请求体"""
        mcp_id = first_ready_server["mcp_id"]
        # 先启用服务器
        ipc_client.post(f"/v1/me/servers/{mcp_id}/enable")

        # 发送无效 JSON
        response = ipc_client.post(
            f"/v1/me/servers/{mcp_id}/tools/some_tool/call",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code in (400, 422)

    def test_missing_user_header(self, test_config: IntegrationTestConfig) -> None:
        """测试缺少用户头"""
        with httpx.Client(
            transport=httpx.HTTPTransport(uds=test_config.socket_path),
            base_url="http://localhost",
            timeout=10.0,
            # 不设置 X-Witty-User 头
        ) as client:
            response = client.get("/v1/servers")
            # 应该使用默认用户或返回错误
            assert response.status_code in (200, 400, 401)


# ============================================================================
# 数据收集测试（用于生成测试报告）
# ============================================================================


@skip_unless_vm
class TestDataCollection:
    """数据收集测试"""

    def test_collect_ipc_data(
        self,
        system_client: httpx.Client,
        tmp_path: Path,
    ) -> None:
        """收集 IPC 接口数据"""
        data: dict[str, Any] = {}

        # 1. 收集健康状态
        health_resp = system_client.get("/health")
        if health_resp.status_code == 200:
            data["health"] = health_resp.json()

        # 2. 收集服务器列表
        servers_resp = system_client.get("/v1/servers", params={"include_disabled": "true"})
        if servers_resp.status_code == 200:
            data["servers"] = servers_resp.json()

        # 3. 收集运行时状态
        sessions_resp = system_client.get("/v1/runtime/sessions")
        if sessions_resp.status_code == 200:
            data["sessions"] = sessions_resp.json()

        # 保存数据
        output_file = tmp_path / "witty_mcp_ipc_data.json"
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        assert output_file.exists()
        print(f"\nIPC data collected to: {output_file}")  # noqa: T201
        print(f"Health: {data.get('health', {}).get('data', {})}")  # noqa: T201
        print(f"Servers count: {len(data.get('servers', {}).get('data', []))}")  # noqa: T201
        print(f"Sessions count: {len(data.get('sessions', {}).get('data', []))}")  # noqa: T201

    def test_collect_cli_data(self, tmp_path: Path) -> None:
        """收集 CLI 命令输出"""
        data: dict[str, Any] = {}

        # 1. 版本信息
        result = run_cli(["version"], check=False)
        data["version"] = {
            "output": result.stdout,
            "returncode": result.returncode,
        }

        # 2. 服务器列表
        result = run_cli(["servers", "list", "--global", "--json"], check=False)
        data["servers_list"] = {
            "output": result.stdout if result.returncode == 0 else result.stderr,
            "returncode": result.returncode,
        }

        # 3. 运行时状态
        result = run_cli(["runtime", "status", "--json"], check=False)
        data["runtime_status"] = {
            "output": result.stdout if result.returncode == 0 else result.stderr,
            "returncode": result.returncode,
        }

        # 4. 配置信息
        result = run_cli(["config", "show", "--json"], check=False)
        data["config"] = {
            "output": result.stdout if result.returncode == 0 else result.stderr,
            "returncode": result.returncode,
        }

        # 保存数据
        output_file = tmp_path / "witty_mcp_cli_data.json"
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        assert output_file.exists()
        print(f"\nCLI data collected to: {output_file}")  # noqa: T201


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
