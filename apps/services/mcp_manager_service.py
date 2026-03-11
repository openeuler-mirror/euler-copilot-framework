"""MCP Manager API 异步客户端"""
import json
import logging
from typing import Any, Self

import aiohttp
import mcp.types as types
from aiohttp import ClientError, ClientResponseError

from apps.models.mcp import MCPTools
from apps.schemas.mcp import MCPServerInfo

UDS_PATH = "/run/witty/mcp-manager.sock"
API_BASE_URL = "http://localhost"
HEADER_X_USER_ID = "X-Witty-User"
HEADER_CONTENT_TYPE = "Content-Type"
CONTENT_TYPE_JSON = "application/json"
RESPONSE_DATA_KEY = "data"
REQUEST_PARAMS_KEY = "arguments"
logger = logging.getLogger(__name__)


class MCPManagerAPI:
    """MCP Manager API 异步客户端"""

    def __init__(self) -> None:
        """
        初始化客户端
        :param config: 配置实例，若为None则使用MCPManagerConfig的默认配置
        """  # noqa: D205
        # 延迟初始化：由异步上下文管理器创建，避免提前占用资源
        self._connector: aiohttp.UnixConnector | None = None
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> Self:
        """异步上下文管理器入口：创建UDS连接器和ClientSession"""
        self._connector = aiohttp.UnixConnector(path=UDS_PATH)
        self._session = aiohttp.ClientSession(
            connector=self._connector,
        )
        return self

    async def __aexit__(self, exc_type: type | None, exc: Exception | None, tb: type | None) -> None:  # noqa: PYI036
        """异步上下文管理器出口：安全释放资源"""
        if self._session:
            await self._session.close()
        # 重置属性，避免重复使用已关闭的资源
        self._session = None
        self._connector = None

    def _build_request_headers(self, user_id: str, content_type: str | None = None) -> dict[str, str]:
        """构建请求头，自定义user_id优先于配置默认值"""
        headers = {HEADER_X_USER_ID: user_id}
        if content_type:
            headers[HEADER_CONTENT_TYPE] = content_type
        return headers

    def _check_session(self) -> None:
        """检查Session是否初始化，未通过async with使用则抛明确异常"""
        if self._session is None:
            msg = (
                "MCPManagerAPI未初始化！请通过异步上下文管理器使用：\n"
                "async with MCPManagerAPI() as api:\n"
                "    await api.get_mcp_list()"
            )
            raise RuntimeError(
                msg,
            )

    def _safe_get_data(self, result: Any, default: Any = None) -> Any:
        """安全获取响应data字段，避免KeyError和非字典类型解析错误"""
        return result.get(RESPONSE_DATA_KEY, default) if isinstance(result, dict) else default

    async def get_mcp_list(self, user_id: str) -> list[MCPServerInfo]:
        """获取MCP列表，返回MCPInfo模型列表"""
        self._check_session()
        url = f"{API_BASE_URL}/v1/servers"
        try:
            async with self._session.get(url, headers=self._build_request_headers(user_id)) as response:
                response.raise_for_status()
                result = await response.json()
                return [MCPServerInfo(**mcp) for mcp in self._safe_get_data(result, [])]
        except (TimeoutError, ClientError, ClientResponseError, json.JSONDecodeError) as e:
            logger.exception(f"获取MCP列表失败 | 用户ID：{user_id} | 错误：{e!s}")  # noqa: G004, TRY401
            return []

    async def get_mcp_tools(self, mcp_id: str, user_id: str) -> list[MCPTools]:
        """获取指定MCP的工具列表，返回MCPTools模型列表"""
        self._check_session()
        url = f"{API_BASE_URL}/v1/servers/{mcp_id}/tools"
        try:
            async with self._session.get(url, headers=self._build_request_headers(user_id)) as response:
                response.raise_for_status()
                result = await response.json()
                data = self._safe_get_data(result, [])
                tools = data.get("tools")
                return [
                    MCPTools(
                        mcpId=mcp_id,
                        toolName=tool.get("name", ""),
                        description=tool.get("description", ""),
                        inputSchema=tool.get("inputSchema", {}),
                        outputSchema=tool.get("outputSchema", {}),
                    ) for tool in tools
                ]
        except (TimeoutError, ClientError, ClientResponseError, json.JSONDecodeError) as e:
            logger.exception(f"获取MCP工具失败 | MCP ID：{mcp_id} | 错误：{e!s}")  # noqa: G004, TRY401
            return []

    async def call_tool(self, mcp_id: str, tool_name: str, params: dict[str, Any], user_id: str):  # noqa: ANN201
        """调用指定MCP的工具，返回工具执行结果"""
        self._check_session()
        url = f"{API_BASE_URL}/v1/me/servers/{mcp_id}/tools/{tool_name}/call"
        try:
            async with self._session.post(
                    url,
                    headers=self._build_request_headers(user_id, CONTENT_TYPE_JSON),
                    json={REQUEST_PARAMS_KEY: params},
            ) as response:
                response.raise_for_status()
                result = await response.json()
                data = self._safe_get_data(result)

                return types.CallToolResult(
                    content=data.get("content"),
                    structuredContent=data.get("structuredContent"),
                    isError=data.get("isError"),
                )
        except (TimeoutError, ClientError, ClientResponseError, json.JSONDecodeError) as e:
            logger.exception(f"调用MCP工具失败 | MCP ID：{mcp_id} | 工具名：{tool_name}| 错误：{e!s}")  # noqa: G004, TRY401
            return None

    async def activate_mcp(self, mcp_id: str, user_id: str) -> bool | None:
        """激活/禁用指定MCP"""
        self._check_session()

        url = f"{API_BASE_URL}/v1/me/servers/{mcp_id}/enable"
        try:
            async with self._session.post(url, headers=self._build_request_headers(user_id)) as response:
                response.raise_for_status()
                return True
        except (TimeoutError, ClientError, ClientResponseError, json.JSONDecodeError) as e:
            logger.exception(f"MCP启用失败 | MCP ID：{mcp_id} | 错误：{e!s}")  # noqa: G004, TRY401
            return False

    async def deactivate_mcp(self, mcp_id: str, user_id: str) -> bool:
        """激活/禁用指定MCP"""
        self._check_session()

        url = f"{API_BASE_URL}/v1/me/servers/{mcp_id}/disable"
        try:
            async with self._session.post(url, headers=self._build_request_headers(user_id)) as response:
                response.raise_for_status()
                return True
        except (TimeoutError, ClientError, ClientResponseError, json.JSONDecodeError) as e:
            logger.exception(f"MCP禁用失败 | MCP ID：{mcp_id} | 错误：{e!s}")  # noqa: G004, TRY401
            return False
