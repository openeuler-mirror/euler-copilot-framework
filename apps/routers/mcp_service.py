# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 语义接口中心相关路由"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from apps.dependency.user import verify_admin, verify_personal_token, verify_session
from apps.schemas.enum_var import SearchType
from apps.schemas.mcp import ActiveMCPServiceRequest, UpdateMCPServiceRequest
from apps.schemas.mcp_service import (
    ActiveMCPServiceRsp,
    BaseMCPServiceOperationMsg,
    DeleteMCPServiceRsp,
    EditMCPServiceMsg,
    GetMCPServiceDetailMsg,
    GetMCPServiceDetailRsp,
    GetMCPServiceListMsg,
    GetMCPServiceListRsp,
    UpdateMCPServiceMsg,
    UpdateMCPServiceRsp,
)
from apps.schemas.response_data import ResponseData
from apps.services.mcp_service import MCPServiceManager

_logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/mcp",
    tags=["mcp-service"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)
admin_router = APIRouter(
    prefix="/api/admin/mcp",
    tags=["mcp-service"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
        Depends(verify_admin),
    ],
)


@router.get("", response_model=GetMCPServiceListRsp | ResponseData)
async def get_mcpservice_list(  # noqa: PLR0913
    request: Request,
    searchType: SearchType = SearchType.ALL,  # noqa: N803
    keyword: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    *,
    isInstall: bool | None = None,  # noqa: N803
    isActive: bool | None = None,  # noqa: N803
) -> JSONResponse:
    """GET /mcp?searchType=xxx&keyword=xxx&page=xxx&isInstall=xxx&isActive=xxx: 获取服务列表"""
    user_id = request.state.user_id
    try:
        service_cards = await MCPServiceManager.fetch_mcp_services(
            searchType,
            user_id,
            keyword,
            page,
            is_install=isInstall,
            is_active=isActive,
        )
    except Exception as e:
        err = f"[MCPServiceCenter] 获取MCP服务列表失败: {e}"
        _logger.exception(err)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            GetMCPServiceListRsp(
                code=status.HTTP_200_OK,
                message="OK",
                result=GetMCPServiceListMsg(
                    currentPage=page,
                    services=service_cards,
                ),
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@admin_router.put("", response_model=UpdateMCPServiceRsp)
async def create_or_update_mcpservice(
    request: Request,
    data: UpdateMCPServiceRequest,
) -> JSONResponse:
    """PUT /mcp: 新建或更新MCP服务"""
    if not data.mcp_id:
        try:
            service_id = await MCPServiceManager.create_mcpservice(data, request.state.user_id)
        except Exception as e:
            _logger.exception("[MCPServiceCenter] MCP服务创建失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=jsonable_encoder(
                    ResponseData(
                        code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        message=f"MCP服务创建失败: {e!s}",
                        result={},
                    ).model_dump(exclude_none=True, by_alias=True),
                ),
            )
    else:
        try:
            service_id = await MCPServiceManager.update_mcpservice(data, request.state.user_id)
        except Exception as e:
            _logger.exception("[MCPService] 更新MCP服务失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=jsonable_encoder(
                    ResponseData(
                        code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        message=f"更新MCP服务失败: {e!s}",
                        result={},
                    ).model_dump(exclude_none=True, by_alias=True),
                ),
            )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            UpdateMCPServiceRsp(
                code=status.HTTP_200_OK,
                message="OK",
                result=UpdateMCPServiceMsg(
                    serviceId=service_id,
                    name=data.name,
                ),
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@admin_router.post("/{serviceId}/install")
async def install_mcp_service(
        request: Request,
        service_id: Annotated[str, Path(..., alias="serviceId", description="服务ID")],
        *,
        install: Annotated[bool, Query(..., description="是否安装")] = True,
) -> JSONResponse:
    """安装MCP服务"""
    try:
        await MCPServiceManager.install_mcpservice(request.state.user_id, service_id, install=install)
    except Exception as e:
        err = f"[MCPService] 安装mcp服务失败: {e!s}" if install else f"[MCPService] 卸载mcp服务失败: {e!s}"
        _logger.exception(err)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message=err,
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ResponseData(
                code=status.HTTP_200_OK,
                message="OK",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@admin_router.get("/{serviceId}", response_model=GetMCPServiceDetailRsp)
async def get_service_detail(
    service_id: Annotated[str, Path(..., alias="serviceId", description="服务ID")],
    *,
    edit: Annotated[bool, Query(..., description="是否为编辑模式")] = False,
) -> JSONResponse:
    """获取MCP服务详情"""
    # 获取MCP服务详情
    try:
        data = await MCPServiceManager.get_mcp_service(service_id)
        config = await MCPServiceManager.get_mcp_config(service_id)
    except Exception as e:
        err = f"[MCPService] 获取MCP服务API失败: {e}"
        _logger.exception(err)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )

    if data is None or config is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_404_NOT_FOUND,
                    message="MCP服务有关信息不存在",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )

    if edit:
        # 组装编辑所需信息
        detail = EditMCPServiceMsg(
            serviceId=service_id,
            name=data.name,
            description=data.description,
            overview=config.overview,
            data=config.model_dump(by_alias=True, exclude_none=True),
            mcpType=config.mcpType,
        )
    else:
        # 组装详情所需信息
        # 从数据库获取工具列表替代data.tools
        tools = await MCPServiceManager.get_mcp_tools(service_id)
        detail = GetMCPServiceDetailMsg(
            serviceId=service_id,
            name=data.name,
            description=data.description,
            overview=config.overview,
            status=data.status,
            tools=tools,
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            GetMCPServiceDetailRsp(
                code=status.HTTP_200_OK,
                message="OK",
                result=detail,
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@admin_router.delete("/{serviceId}", response_model=DeleteMCPServiceRsp)
async def delete_service(serviceId: Annotated[str, Path()]) -> JSONResponse:  # noqa: N803
    """删除服务"""
    try:
        await MCPServiceManager.delete_mcpservice(serviceId)
    except Exception as e:
        err = f"[MCPServiceManager] 删除MCP服务失败: {e}"
        _logger.exception(err)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            DeleteMCPServiceRsp(
                code=status.HTTP_200_OK,
                message="OK",
                result=BaseMCPServiceOperationMsg(serviceId=serviceId),
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@router.post("/{mcpId}", response_model=ActiveMCPServiceRsp)
async def active_or_deactivate_mcp_service(
    request: Request,
    mcpId: Annotated[str, Path()],  # noqa: N803
    data: ActiveMCPServiceRequest,
) -> JSONResponse:
    """激活/取消激活mcp"""
    try:
        if data.active:
            await MCPServiceManager.active_mcpservice(request.state.user_id, mcpId, data.mcp_env)
        else:
            await MCPServiceManager.deactive_mcpservice(request.state.user_id, mcpId)
    except Exception as e:
        err = f"[MCPService] 激活mcp服务失败: {e!s}" if data.active else f"[MCPService] 取消激活mcp服务失败: {e!s}"
        _logger.exception(err)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message=err,
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ActiveMCPServiceRsp(
                code=status.HTTP_200_OK,
                message="OK",
                result=BaseMCPServiceOperationMsg(serviceId=mcpId),
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )
