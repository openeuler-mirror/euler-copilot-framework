"""
Registry 路由

提供 MCP Server 列表、详情、启用/禁用等 API。
系统级配置只读，由 RPM 管理；用户仅可配置凭据和启用状态。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam

from witty_mcp_manager.ipc.auth import UserContext, get_user_context
from witty_mcp_manager.ipc.schemas import (
    ConfigureRequest,
    ConfigureResponse,
    ConfigureResult,
    DepsMissing,
    DiagnosticsInfo,
    EffectiveConfigInfo,
    EnableDisableResponse,
    EnableDisableResult,
    ServerDetail,
    ServerDetailResponse,
    ServerListResponse,
    ServerSummary,
)
from witty_mcp_manager.registry.models import Override, ServerRecord, TransportType

if TYPE_CHECKING:
    from witty_mcp_manager.ipc.server import IPCServer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Registry"])

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


def _determine_server_status(srv: ServerRecord) -> tuple[str, str | None]:
    """
    确定 Server 状态

    Returns:
        (status, status_reason) 元组

    """
    if not srv.diagnostics:
        return "ready", None

    diag = srv.diagnostics

    # 检查命令是否允许
    if not diag.command_allowed:
        # 从配置中获取命令信息
        command_str = ""
        if srv.default_config.stdio:
            command_str = srv.default_config.stdio.command
        if command_str:
            return "unavailable", f"命令不在白名单中: {command_str}"
        return "unavailable", "命令不在白名单中"

    # 检查是否有错误
    if diag.errors:
        return "unavailable", diag.errors[0]

    # 检查依赖
    if diag.deps_missing:
        missing_parts = []
        if diag.deps_missing.get("system"):
            missing_parts.append(f"系统依赖: {', '.join(diag.deps_missing['system'])}")
        if diag.deps_missing.get("python"):
            missing_parts.append(f"Python 依赖: {', '.join(diag.deps_missing['python'])}")
        if missing_parts:
            return "degraded", f"缺少{'; '.join(missing_parts)}"

    return "ready", None


def _validate_configure_request(transport: TransportType, request: ConfigureRequest) -> None:
    """校验配置请求：env 仅 STDIO，headers 仅 SSE/HTTP"""
    if request.env is not None and transport != TransportType.STDIO:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_ENV",
                "message": "env 仅支持 STDIO transport",
            },
        )
    if request.headers is not None and transport not in (TransportType.SSE, TransportType.STREAMABLE_HTTP):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_HEADERS",
                "message": "headers 仅支持 SSE/Streamable HTTP transport",
            },
        )


def _apply_configure_request(
    override: Override,
    request: ConfigureRequest,
) -> None:
    """应用配置请求到 override"""
    if request.env is not None:
        override.env = request.env
    if request.headers is not None:
        override.headers = request.headers


def _build_configure_result(mcp_id: str, override: Override) -> ConfigureResult:
    """构建配置结果（返回 secret:// 引用）"""
    return ConfigureResult(
        mcp_id=mcp_id,
        env=override.env,
        headers=override.headers,
        updated_at=datetime.now(UTC),
    )


@router.get("/servers", response_model=ServerListResponse)
async def list_servers(
    user: Annotated[UserContext, Depends(get_user_context)],
    *,
    include_disabled: Annotated[bool, Query(description="是否包含系统级禁用的 Server")] = False,
) -> ServerListResponse:
    """
    列出所有 MCP Servers

    只返回系统层已启用的 MCP（除非 include_disabled=true）
    """
    server = get_server()
    result: list[ServerSummary] = []

    for srv in server.list_servers():
        # 解析生效配置
        effective = server.overlay_resolver.resolve(srv, user.user_id)

        # 系统层禁用检查（全局 overlay）
        global_override = server.overlay_storage.load_override(srv.id)
        system_disabled = global_override.disabled if global_override else False

        if system_disabled and not include_disabled:
            continue

        # 确定状态
        status, status_reason = _determine_server_status(srv)

        result.append(
            ServerSummary(
                mcp_id=srv.id,
                name=srv.name,
                summary=srv.summary,
                source=srv.source.value,
                status=status,
                status_reason=status_reason,
                user_enabled=not effective.disabled,
            ),
        )

    return ServerListResponse(data=result)


@router.get("/servers/{mcp_id}", response_model=ServerDetailResponse)
async def get_server_detail(
    mcp_id: Annotated[str, PathParam(description="MCP Server ID")],
    user: Annotated[UserContext, Depends(get_user_context)],
) -> ServerDetailResponse:
    """获取 MCP Server 详情"""
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

    # 解析生效配置
    effective = server.overlay_resolver.resolve(srv, user.user_id)

    # 确定状态
    status, status_reason = _determine_server_status(srv)

    # 构建诊断信息
    diagnostics_info = None
    if srv.diagnostics:
        diag = srv.diagnostics
        # 从配置中获取命令信息
        command_str = ""
        if srv.default_config.stdio:
            command_str = srv.default_config.stdio.command
        diagnostics_info = DiagnosticsInfo(
            command_allowed=diag.command_allowed,
            command=command_str,
            allowed_commands=[],  # 可以从 allowlist 获取，但这里暂时为空
            deps_missing=DepsMissing(
                system=diag.deps_missing.get("system", []),
                python=diag.deps_missing.get("python", []),
            )
            if diag.deps_missing
            else None,
            files_valid=not diag.errors,
            errors=diag.errors,
        )

    # 构建生效配置信息
    effective_config_info = EffectiveConfigInfo(
        transport=effective.config.transport.value,
        tool_call_timeout_sec=effective.timeouts.tool_call,
        idle_ttl_sec=effective.timeouts.idle_ttl,
        max_concurrency=effective.concurrency.max_per_user,
        env=effective.env,
    )

    return ServerDetailResponse(
        data=ServerDetail(
            mcp_id=srv.id,
            name=srv.name,
            summary=srv.summary,
            description=srv.summary,
            source=srv.source.value,
            transport=srv.default_config.transport.value,
            install_root=srv.install_root,
            upstream_key=srv.upstream_key,
            status=status,
            status_reason=status_reason,
            user_enabled=not effective.disabled,
            diagnostics=diagnostics_info,
            effective_config=effective_config_info,
        ),
    )


@router.post("/me/servers/{mcp_id}:enable", response_model=EnableDisableResponse)
async def enable_server(
    mcp_id: Annotated[str, PathParam(description="MCP Server ID")],
    user: Annotated[UserContext, Depends(get_user_context)],
) -> EnableDisableResponse:
    """用户级启用 MCP Server"""
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

    # 创建或更新用户 overlay
    override = server.overlay_storage.load_override(mcp_id, user.user_id)
    if override:
        override.disabled = False
    else:
        override = Override(scope=f"user/{user.user_id}", disabled=False)

    server.overlay_storage.save_override(mcp_id, override, user.user_id)

    logger.info("User %s enabled server %s", user.user_id, mcp_id)

    return EnableDisableResponse(
        data=EnableDisableResult(mcp_id=mcp_id, enabled=True),
    )


@router.post("/me/servers/{mcp_id}:disable", response_model=EnableDisableResponse)
async def disable_server(
    mcp_id: Annotated[str, PathParam(description="MCP Server ID")],
    user: Annotated[UserContext, Depends(get_user_context)],
) -> EnableDisableResponse:
    """用户级禁用 MCP Server"""
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

    # 创建或更新用户 overlay
    override = server.overlay_storage.load_override(mcp_id, user.user_id)
    if override:
        override.disabled = True
    else:
        override = Override(scope=f"user/{user.user_id}", disabled=True)

    server.overlay_storage.save_override(mcp_id, override, user.user_id)

    # 停止该用户的会话（如果存在）
    session = await server.runtime_manager.get_session(user.user_id, mcp_id)
    if session and session.is_running:
        await session.stop()
        logger.info("Stopped session for disabled server %s (user=%s)", mcp_id, user.user_id)

    logger.info("User %s disabled server %s", user.user_id, mcp_id)

    return EnableDisableResponse(
        data=EnableDisableResult(mcp_id=mcp_id, enabled=False),
    )


@router.post("/me/servers/{mcp_id}:configure", response_model=ConfigureResponse)
async def configure_server(
    mcp_id: Annotated[str, PathParam(description="MCP Server ID")],
    user: Annotated[UserContext, Depends(get_user_context)],
    request: ConfigureRequest,
) -> ConfigureResponse:
    """
    用户级配置 MCP Server

    用户可配置 env（STDIO）或 headers（SSE/HTTP）中的凭据。
    请求传明文，Manager 存储后返回 secret:// 引用。
    timeouts/concurrency 由系统统一管理，用户不可自定义。
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

    _validate_configure_request(srv.default_config.transport, request)

    scope = f"user/{user.user_id}"
    override = server.overlay_storage.load_override(mcp_id, user.user_id)
    if override is None:
        override = Override(scope=scope)

    _apply_configure_request(override, request)

    server.overlay_storage.save_override(mcp_id, override, user.user_id)

    logger.info("User %s configured server %s", user.user_id, mcp_id)

    return ConfigureResponse(
        data=_build_configure_result(mcp_id, override),
    )
