import asyncio
import json
import logging
import types
from typing import Any, Self

import aiohttp
import mcp.types as types
from aiohttp import ClientError, ClientResponseError

# 项目内模块导入（保持你的原有导入）
from apps.models.mcp import MCPTools
from apps.schemas.mcp_manager import MCPManagerConfig, MCPServerInfo

# 固定配置（无环境区分，完全按你的要求）
UDS_PATH = "/run/witty/mcp-manager.sock"
API_BASE_URL = "http://localhost/v1"  # localhost仅为UDS占位，不可修改

# 日志配置（替代print，生产环境友好，可直接集成到项目全局日志）
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp-manager-api")


class MCPManagerAPI:
    """MCP Manager API 异步客户端（无环境区分，基于UDS连接）"""

    HEADER_X_USER_ID = "X-User-ID"
    HEADER_CONTENT_TYPE = "Content-Type"
    CONTENT_TYPE_JSON = "application/json"
    RESPONSE_DATA_KEY = "data"
    REQUEST_PARAMS_KEY = "params"

    def __init__(self, config: MCPManagerConfig | None = None) -> None:
        """
        初始化客户端
        :param config: 配置实例，若为None则使用MCPManagerConfig的默认配置
        """  # noqa: D205
        self.config = config or MCPManagerConfig()
        # 延迟初始化：由异步上下文管理器创建，避免提前占用资源
        self._connector: aiohttp.UnixConnector | None = None
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> Self:
        """异步上下文管理器入口：创建UDS连接器和ClientSession"""
        self._connector = aiohttp.UnixConnector(path=self.config.uds_path)
        self._session = aiohttp.ClientSession(
            connector=self._connector,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )
        return self

    async def __aexit__(self, exc_type: type | None, exc: Exception | None, tb) -> None:  # noqa: PYI036
        """异步上下文管理器出口：安全释放资源（Session自动关闭连接器，无需手动操作）"""
        if self._session:
            await self._session.close()
        # 重置属性，避免重复使用已关闭的资源
        self._session = None
        self._connector = None

    def _build_request_headers(self, user_id: str | None = None, content_type: str | None = None) -> Dict[str, str]:
        """构建请求头，自定义user_id优先于配置默认值"""
        headers = {self.HEADER_X_USER_ID: user_id or self.config.user_id}
        if content_type:
            headers[self.HEADER_CONTENT_TYPE] = content_type
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
        return result.get(self.RESPONSE_DATA_KEY, default) if isinstance(result, dict) else default

    async def get_mcp_list(self, user_id: str | None = None) -> list[MCPServerInfo]:
        """获取MCP列表，返回MCPInfo模型列表"""
        self._check_session()
        url = f"{API_BASE_URL}/servers"
        try:
            async with self._session.get(url, headers=self._build_request_headers(user_id)) as response:
                response.raise_for_status()  # 非2xx状态码抛出异常
                result = await response.json()
                return [MCPServerInfo(**mcp) for mcp in self._safe_get_data(result, [])]
        except (TimeoutError, ClientError, ClientResponseError, json.JSONDecodeError) as e:
            logger.error(f"获取MCP列表失败 | 用户ID：{user_id or self.config.user_id} | 错误：{e!s}", exc_info=True)  # noqa: G004
            return []

    async def get_mcp_tools(self, mcp_id: str, user_id: str | None = None) -> list[MCPTools]:
        """获取指定MCP的工具列表，返回MCPTools模型列表"""
        self._check_session()
        url = f"{API_BASE_URL}/servers/{mcp_id}/tools"
        try:
            async with self._session.get(url, headers=self._build_request_headers(user_id)) as response:
                response.raise_for_status()
                result = await response.json()
                # 简化列表推导式，保持你的原有字段映射逻辑
                return [
                    MCPTools(
                        mcpId=mcp_id,
                        toolName=tool.get("toolName", ""),
                        description=tool.get("description", ""),
                        inputSchema=tool.get("inputSchema", {}),
                        outputSchema=tool.get("outputSchema", {})
                    ) for tool in self._safe_get_data(result, [])
                ]
        except (TimeoutError, ClientError, ClientResponseError, json.JSONDecodeError) as e:
            logger.error(f"获取MCP工具失败 | MCP ID：{mcp_id} | 用户ID：{user_id or self.config.user_id} | 错误：{e!s}", exc_info=True)  # noqa: G004, G201
            return []

    async def call_tool(self, mcp_id: str, tool_name: str, params: dict[str, Any], user_id: str | None = None):  # noqa: ANN201
        """调用指定MCP的工具，返回工具执行结果"""
        self._check_session()
        url = f"{API_BASE_URL}/servers/{mcp_id}/tools/{tool_name}/call"
        try:
            async with self._session.post(
                url,
                headers=self._build_request_headers(user_id, self.CONTENT_TYPE_JSON),
                json={self.REQUEST_PARAMS_KEY: params}
            ) as response:
                response.raise_for_status()
                result = await response.json()
                data = self._safe_get_data(result)

                return types.CallToolResult(
                    content=data.get("content"),
                    structuredContent=data.get("structuredContent"),
                    isError=data.get("isError")
                )
        except (TimeoutError, ClientError, ClientResponseError, json.JSONDecodeError) as e:
            logger.error(f"调用MCP工具失败 | MCP ID：{mcp_id} | 工具名：{tool_name} | 用户ID：{user_id or self.config.user_id} | 错误：{e!s}", exc_info=True)  # noqa: G004, G201
            return None

    async def activate_mcp(self, mcp_id: str, user_id: str | None = None) -> bool | None:
        """激活/禁用指定MCP"""
        self._check_session()
        # 保留你最新的URL拼接逻辑：mcp_id + 枚举value
        url = f"{API_BASE_URL}/servers/{mcp_id}/enable"
        try:
            async with self._session.post(url, headers=self._build_request_headers(user_id)) as response:
                response.raise_for_status()
                return True
        except (TimeoutError, ClientError, ClientResponseError, json.JSONDecodeError) as e:
            logger.error(f"MCP启用失败 | MCP ID：{mcp_id} | 用户ID：{user_id or self.config.user_id} | 错误：{e!s}", exc_info=True)  # noqa: G004, G201
            return False

    async def deactive_mcp(self, mcp_id: str, user_id: str | None = None) -> bool:
        """激活/禁用指定MCP"""
        self._check_session()
        # 保留你最新的URL拼接逻辑：mcp_id + 枚举value
        url = f"{API_BASE_URL}/servers/{mcp_id}/disable"
        try:
            async with self._session.post(url, headers=self._build_request_headers(user_id)) as response:
                response.raise_for_status()
                return True
        except (TimeoutError, ClientError, ClientResponseError, json.JSONDecodeError) as e:
            logger.error(f"MCP禁用失败 | MCP ID：{mcp_id} | 用户ID：{user_id or self.config.user_id} | 错误：{e!s}", exc_info=True)  # noqa: G004, G201
            return False
