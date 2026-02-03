"""
Tools 路由

提供 Tools 发现和调用 API。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam

from witty_mcp_manager.exceptions import AdapterError, WittyRuntimeError
from witty_mcp_manager.ipc.auth import UserContext, get_user_context
from witty_mcp_manager.ipc.schemas import (
    CacheInfo,
    ContentItem,
    ToolCallMetadata,
    ToolCallRequest,
    ToolCallResponse,
    ToolSchema,
    ToolsListResponse,
    ToolsListResult,
)
from witty_mcp_manager.ipc.schemas import (
    ToolCallResult as ToolCallResultSchema,
)

if TYPE_CHECKING:
    from witty_mcp_manager.ipc.server import IPCServer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Tools"])

# 服务器实例引用
_server: IPCServer | None = None


def set_server(server: IPCServer) -> None:
    """设置服务器实例"""
    global _server  # noqa: PLW0603
    _server = server


def get_server() -> IPCServer:
    """获取服务器实例"""
    if _server is None:
        msg = "Server not initialized"
        raise RuntimeError(msg)
    return _server


@router.get("/servers/{mcp_id}/tools", response_model=ToolsListResponse)
async def list_tools(
    mcp_id: Annotated[str, PathParam(description="MCP Server ID")],
    user: Annotated[UserContext, Depends(get_user_context)],
    *,
    force_refresh: Annotated[bool, Query(description="强制刷新缓存")] = False,
) -> ToolsListResponse:
    """
    获取 MCP Server 的 Tools 列表

    支持缓存，默认 10 分钟过期
    """
    server = get_server()

    srv = server.get_server(mcp_id)
    if not srv:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SERVER_NOT_FOUND",
                "message": f"MCP Server not found: {mcp_id}",
            },
        )

    # 检查是否启用
    effective = server.overlay_resolver.resolve(srv, user.user_id)
    if effective.disabled:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "SERVER_DISABLED",
                "message": f"MCP Server is disabled: {mcp_id}",
            },
        )

    try:
        # 获取或创建会话
        session = await server.runtime_manager.get_or_create_session(
            srv, effective, user.user_id
        )

        # 获取适配器
        adapter = await server.get_or_create_adapter(srv, session)

        # 发现 tools
        tools = await adapter.discover_tools(force_refresh=force_refresh)

        # 获取缓存信息
        cache_info = _get_cache_info(adapter, force_refresh=force_refresh)

        return ToolsListResponse(
            data=ToolsListResult(
                tools=[
                    ToolSchema(
                        name=t.name,
                        description=t.description,
                        inputSchema=t.input_schema,
                    )
                    for t in tools
                ],
                cache_info=cache_info,
            ),
        )

    except AdapterError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "ADAPTER_ERROR",
                "message": str(e),
            },
        ) from e
    except WittyRuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "RUNTIME_ERROR",
                "message": str(e),
            },
        ) from e


def _get_cache_info(adapter: object, *, force_refresh: bool) -> CacheInfo | None:
    """获取缓存信息"""
    # 访问适配器的缓存（通过公共方法）
    cache = getattr(adapter, "get_tools_cache", lambda: None)()
    if cache is None:
        return None

    return CacheInfo(
        cached_at=cache.cached_at,
        expires_at=cache.cached_at + timedelta(seconds=cache.ttl_seconds),
        from_cache=not force_refresh,
    )


@router.post("/me/servers/{mcp_id}/tools/{tool_name}:call", response_model=ToolCallResponse)
async def call_tool(
    mcp_id: Annotated[str, PathParam(description="MCP Server ID")],
    tool_name: Annotated[str, PathParam(description="Tool 名称")],
    user: Annotated[UserContext, Depends(get_user_context)],
    request: ToolCallRequest,
) -> ToolCallResponse:
    """
    调用 MCP Tool

    支持自定义超时时间
    """
    server = get_server()

    srv = server.get_server(mcp_id)
    if not srv:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SERVER_NOT_FOUND",
                "message": f"MCP Server not found: {mcp_id}",
            },
        )

    # 检查是否启用
    effective = server.overlay_resolver.resolve(srv, user.user_id)
    if effective.disabled:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "SERVER_DISABLED",
                "message": f"MCP Server is disabled: {mcp_id}",
            },
        )

    start_time = datetime.now(UTC)
    timeout_ms_default = effective.timeouts.tool_call * 1000

    try:
        # 获取或创建会话
        session = await server.runtime_manager.get_or_create_session(
            srv, effective, user.user_id
        )

        # 更新最后使用时间
        session.touch()

        # 获取适配器
        adapter = await server.get_or_create_adapter(srv, session)

        # 计算超时
        timeout_ms = request.timeout_ms or timeout_ms_default

        # 调用 tool
        result = await adapter.call_tool(
            tool_name=tool_name,
            arguments=request.arguments,
            timeout_ms=timeout_ms,
        )

        # 计算耗时
        duration_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

        return ToolCallResponse(
            data=ToolCallResultSchema(
                content=[
                    ContentItem(
                        type=item.get("type", "text"),
                        text=item.get("text"),
                        data=item.get("data"),
                        mimeType=item.get("mimeType"),
                    )
                    for item in result.content
                ],
                isError=result.is_error,
            ),
            metadata=ToolCallMetadata(
                duration_ms=duration_ms,
                mcp_id=mcp_id,
                tool_name=tool_name,
            ),
        )

    except TimeoutError as e:
        duration_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
        raise HTTPException(
            status_code=504,
            detail={
                "code": "TOOL_CALL_TIMEOUT",
                "message": f"Tool call timed out after {duration_ms}ms",
            },
        ) from e
    except AdapterError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "ADAPTER_ERROR",
                "message": str(e),
            },
        ) from e
    except WittyRuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "RUNTIME_ERROR",
                "message": str(e),
            },
        ) from e
