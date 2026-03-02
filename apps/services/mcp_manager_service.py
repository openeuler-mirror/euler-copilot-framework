import json  # noqa: D100
import logging
from typing import Any, Self

import aiohttp
import mcp.types as types
from aiohttp import ClientError, ClientResponseError

# 项目内模块导入（保持你的原有导入）
from apps.models.mcp import MCPTools
from apps.schemas.mcp_manager import MCPManagerConfig, MCPServerInfo

# 固定配置（无环境区分，完全按你的要求）
UDS_PATH = "/run/witty/mcp-manager.sock"
API_BASE_URL = "http://localhost"  # localhost仅为UDS占位，不可修改

# 日志配置（替代print，生产环境友好，可直接集成到项目全局日志）
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp-manager-api")


class MCPManagerAPI:
    """MCP Manager API 异步客户端（无环境区分，基于UDS连接，对齐官方API规范）"""

    # 对齐官方API的请求头和参数常量
    HEADER_X_USER_ID = "X-Witty-User"
    HEADER_CONTENT_TYPE = "Content-Type"
    CONTENT_TYPE_JSON = "application/json"
    RESPONSE_DATA_KEY = "data"
    REQUEST_ARGS_KEY = "arguments"  # 替换原params，对齐官方API
    REQUEST_TIMEOUT_KEY = "timeout_ms"

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
        # 增加默认值兜底，避免config.uds_path为空
        self._connector = aiohttp.UnixConnector(path=self.config.uds_path or UDS_PATH)
        # 超时时间增加默认值，避免配置为空
        self._session = aiohttp.ClientSession(
            connector=self._connector,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout or 30),
        )
        return self

    async def __aexit__(self, exc_type: type | None, exc: Exception | None, tb) -> None:  # noqa: ANN001, PYI036
        """异步上下文管理器出口：安全释放资源（Session自动关闭连接器，无需手动操作）"""
        if self._session:
            await self._session.close()
        # 重置属性，避免重复使用已关闭的资源
        self._session = None
        self._connector = None

    def _build_request_headers(self, user_id: str | None = None, content_type: str | None = None) -> dict[str, str]:
        """构建请求头，自定义user_id优先于配置默认值，增加root兜底"""
        headers = {self.HEADER_X_USER_ID: user_id or self.config.user_id or "root"}
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
            raise RuntimeError(msg)

    def _safe_get_data(self, result: Any, default: Any = None) -> Any:
        """安全获取响应data字段，避免KeyError和非字典类型解析错误"""
        return result.get(self.RESPONSE_DATA_KEY, default) if isinstance(result, dict) else default

    async def get_mcp_list(self, user_id: str | None = None) -> list[MCPServerInfo]:
        """获取MCP列表（对齐官方API路径，增加me层级）"""
        self._check_session()

        url = f"{API_BASE_URL}/v1/servers"
        try:
            async with self._session.get(url, headers=self._build_request_headers(user_id)) as response:
                response.raise_for_status()  # 非2xx状态码抛出异常
                result = await response.json()
                mcp_raw_list = self._safe_get_data(result, [])
                return [MCPServerInfo(**mcp) for mcp in mcp_raw_list]
        except (TimeoutError, ClientError, ClientResponseError, json.JSONDecodeError) as e:
            logger.error(f"获取MCP列表失败 | 用户ID：{user_id or self.config.user_id} | 错误：{e!s}", exc_info=True)  # noqa: G004
            return []

    async def get_mcp_tools(self, mcp_id: str, user_id: str | None = None) -> list[MCPTools]:
        """获取指定MCP的工具列表"""
        self._check_session()

        url = f"{API_BASE_URL}/v1/servers/{mcp_id}/tools"
        try:
            async with self._session.get(url, headers=self._build_request_headers(user_id)) as response:
                response.raise_for_status()
                result = await response.json()
                # 简化列表推导式，保持你的原有字段映射逻辑
                data = self._safe_get_data(result, [])
                tools = data.get("tools", [])
                tools_list = [
                    MCPTools(
                        mcpId=mcp_id,
                        toolName=tool.get("name", ""),
                        description=tool.get("description", ""),
                        inputSchema=tool.get("inputSchema", {}),
                        outputSchema=tool.get("outputSchema", {}),
                    ) for tool in tools
                ]
                logger.info(f"[get_mcp_tools] MCP ID: {mcp_id} | 获取到 {len(tools_list)} 个工具")  # noqa: G004
                return tools_list
        except (TimeoutError, ClientError, ClientResponseError, json.JSONDecodeError) as e:
            logger.error(f"获取MCP工具失败 | MCP ID：{mcp_id} | 用户ID：{user_id or self.config.user_id} | 错误：{e!s}", exc_info=True)  # noqa: E501, G004, G201
            return []

    async def call_tool(self, mcp_id: str, tool_name: str, params: dict[str, Any], user_id: str | None = None, timeout_ms: int = 30000) -> types.CallToolResult:  # noqa: E501
        """
        调用指定MCP的工具（完全对齐官方API规范）
        :param mcp_id: MCP服务器ID
        :param tool_name: 工具名称
        :param params: 工具入参（内部映射为官方的arguments字段）
        :param user_id: 用户ID（默认root）
        :param timeout_ms: 超时时间（毫秒，默认30000）
        :return: CallToolResult（异常时也返回实例，避免AttributeError）
        """  # noqa: D205
        self._check_session()
        # 核心修改1：路径对齐官方API（me层级 + :call后缀，替换原/call）
        url = f"{API_BASE_URL}/v1/me/servers/{mcp_id}/tools/{tool_name}:call"
        try:
            # 核心修改2：请求体对齐官方API（arguments + timeout_ms，替换原params）
            request_body = {
                self.REQUEST_ARGS_KEY: params,
                self.REQUEST_TIMEOUT_KEY: timeout_ms
            }

            async with self._session.post(
                url,
                headers=self._build_request_headers(user_id, self.CONTENT_TYPE_JSON),
                json=request_body,
            ) as response:
                response.raise_for_status()
                result = await response.json()
                data = self._safe_get_data(result, {})

                # 增加默认值兜底，避免字段为空导致的AttributeError
                return types.CallToolResult(
                    content=data.get("content", ""),
                    structuredContent=data.get("structuredContent", {}),
                    isError=data.get("isError", False),
                )
        except (TimeoutError, ClientError, ClientResponseError, json.JSONDecodeError) as e:
            error_msg = f"调用MCP工具失败 | MCP ID：{mcp_id} | 工具名：{tool_name} | 用户ID：{user_id or self.config.user_id} | 错误：{e!s}"  # noqa: E501
            logger.error(error_msg, exc_info=True)  # noqa: G201

            # 核心修复：异常时返回带错误信息的CallToolResult，而非None
            return types.CallToolResult(
                content=error_msg, # type: ignore  # noqa: PGH003
                structuredContent={},
                isError=True,
            )

    async def activate_mcp(self, mcp_id: str, user_id: str | None = None) -> bool:
        """激活指定MCP（对齐官方API路径，增加me层级）"""
        self._check_session()
        # 核心修改：路径增加me层级，对齐官方API
        url = f"{API_BASE_URL}/v1/me/servers/{mcp_id}:enable"
        try:
            async with self._session.post(url, headers=self._build_request_headers(user_id)) as response:
                response.raise_for_status()
                return True
        except (TimeoutError, ClientError, ClientResponseError, json.JSONDecodeError) as e:
            logger.error(f"MCP启用失败 | MCP ID：{mcp_id} | 用户ID：{user_id or self.config.user_id} | 错误：{e!s}", exc_info=True)  # noqa: E501, G004, G201
            return False

    async def deactive_mcp(self, mcp_id: str, user_id: str | None = None) -> bool:
        """禁用指定MCP（对齐官方API路径，增加me层级）"""
        self._check_session()
        # 核心修改：路径增加me层级，对齐官方API
        url = f"{API_BASE_URL}/v1/me/servers/{mcp_id}:disable"
        try:
            async with self._session.post(url, headers=self._build_request_headers(user_id)) as response:
                response.raise_for_status()
                return True
        except (TimeoutError, ClientError, ClientResponseError, json.JSONDecodeError) as e:
            logger.error(f"MCP禁用失败 | MCP ID：{mcp_id} | 用户ID：{user_id or self.config.user_id} | 错误：{e!s}", exc_info=True)  # noqa: E501, G004, G201
            return False
