# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""FastAPI 语义接口中心相关路由"""

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile, status
from fastapi.responses import JSONResponse

from apps.dependency.user import get_user, verify_user
from apps.schemas.enum_var import SearchType
from apps.schemas.request_data import ActiveMCPServiceRequest, UpdateMCPServiceRequest
from apps.schemas.response_data import (
    ActiveMCPServiceRsp,
    BaseMCPServiceOperationMsg,
    DeleteMCPServiceRsp,
    EditMCPServiceMsg,
    GetMCPServiceDetailMsg,
    GetMCPServiceDetailRsp,
    GetMCPServiceListMsg,
    GetMCPServiceListRsp,
    ResponseData,
    UpdateMCPServiceMsg,
    UpdateMCPServiceRsp,
    UploadMCPServiceIconMsg,
    UploadMCPServiceIconRsp,
)
from apps.services.mcp_service import MCPServiceManager
from apps.services.user import UserManager

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/mcp",
    tags=["mcp-service"],
    dependencies=[Depends(verify_user)],
)


async def _check_user_admin(user_sub: str) -> None:
    user = await UserManager.get_userinfo_by_user_sub(user_sub)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户未登录")
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="非管理员无法访问")


@router.get("", response_model=GetMCPServiceListRsp | ResponseData)
async def get_mcpservice_list(
        user_sub: Annotated[str, Depends(get_user)],
        search_type: Annotated[
            SearchType, Query(..., alias="searchType", description="搜索类型"),
        ] = SearchType.ALL,
        keyword: Annotated[str | None, Query(..., alias="keyword", description="搜索关键字")] = None,
        page: Annotated[int, Query(..., alias="page", ge=1, description="页码")] = 1,
) -> JSONResponse:
    """获取服务列表"""
    try:
        service_cards = await MCPServiceManager.fetch_mcp_services(
            search_type,
            user_sub,
            keyword,
            page,
        )
    except Exception as e:
        err = f"[MCPServiceCenter] 获取MCP服务列表失败: {e}"
        logger.exception(err)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=GetMCPServiceListRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=GetMCPServiceListMsg(
                currentPage=page,
                services=service_cards,
            ),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.post("", response_model=UpdateMCPServiceRsp)
async def create_or_update_mcpservice(
        user_sub: Annotated[str, Depends(get_user)],  # TODO: get_user直接获取所有用户信息
        data: UpdateMCPServiceRequest,
) -> JSONResponse:
    """新建或更新MCP服务"""
    await _check_user_admin(user_sub)

    if not data.service_id:
        try:
            service_id = await MCPServiceManager.create_mcpservice(data, user_sub)
        except Exception as e:
            logger.exception("[MCPServiceCenter] MCP服务创建失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message=f"MCP服务创建失败: {e!s}",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
    else:
        try:
            service_id = await MCPServiceManager.update_mcpservice(data, user_sub)
        except Exception as e:
            logger.exception("[MCPService] 更新MCP服务失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message=f"更新MCP服务失败: {e!s}",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
    return JSONResponse(status_code=status.HTTP_200_OK, content=UpdateMCPServiceRsp(
        code=status.HTTP_200_OK,
        message="OK",
        result=UpdateMCPServiceMsg(
            serviceId=service_id,
            name=data.name,
        ),
    ).model_dump(exclude_none=True, by_alias=True))


@router.get("/{serviceId}", response_model=GetMCPServiceDetailRsp)
async def get_service_detail(
        user_sub: Annotated[str, Depends(get_user)],
        service_id: Annotated[str, Path(..., alias="serviceId", description="服务ID")],
        *,
        edit: Annotated[bool, Query(..., description="是否为编辑模式")] = False,
) -> JSONResponse:
    """获取MCP服务详情"""
    # 检查用户权限
    if edit:
        await _check_user_admin(user_sub)

    # 获取MCP服务详情
    try:
        data = await MCPServiceManager.get_mcp_service(service_id)
        config, icon = await MCPServiceManager.get_mcp_config(service_id)
    except Exception as e:
        err = f"[MCPService] 获取MCP服务API失败: {e}"
        logger.exception(err)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )

    if edit:
        # 组装编辑所需信息
        detail = EditMCPServiceMsg(
            serviceId=service_id,
            icon=icon,
            name=data.name,
            description=data.description,
            overview=config.overview,
            data=json.dumps(
                config.config.model_dump(by_alias=True, exclude_none=True),
                indent=4,
                ensure_ascii=False,
            ),
            mcpType=config.type,
        )
    else:
        # 组装详情所需信息
        detail = GetMCPServiceDetailMsg(
            serviceId=service_id,
            icon=icon,
            name=data.name,
            description=data.description,
            overview=config.overview,
            tools=data.tools,
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=GetMCPServiceDetailRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=detail,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.delete("/{serviceId}", response_model=DeleteMCPServiceRsp)
async def delete_service(
        user_sub: Annotated[str, Depends(get_user)],
        service_id: Annotated[str, Path(..., alias="serviceId", description="服务ID")],
) -> JSONResponse:
    """删除服务"""
    await _check_user_admin(user_sub)

    try:
        await MCPServiceManager.delete_mcpservice(service_id)
    except Exception as e:
        err = f"[MCPServiceManager] 删除MCP服务失败: {e}"
        logger.exception(err)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=DeleteMCPServiceRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=BaseMCPServiceOperationMsg(serviceId=service_id),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.post("/icon", response_model=UpdateMCPServiceRsp)
async def update_mcp_icon(
        user_sub: Annotated[str, Depends(get_user)],
        service_id: Annotated[str, Path(..., alias="serviceId", description="服务ID")],
        icon: Annotated[UploadFile, File(..., description="图标文件")],
) -> JSONResponse:
    """更新MCP服务图标"""
    await _check_user_admin(user_sub)

    # 检查当前MCP是否存在
    try:
        await MCPServiceManager.get_mcp_service(service_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"MCP服务未找到: {e!s}") from e

    # 判断文件的size
    if not icon.size or icon.size == 0 or icon.size > 1024 * 1024 * 1:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="图标文件为空或超过1MB",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    try:
        url = await MCPServiceManager.save_mcp_icon(service_id, icon)
    except Exception as e:
        err = f"[MCPServiceManager] 更新MCP服务图标失败: {e}"
        logger.exception(err)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=err,
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=UploadMCPServiceIconRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=UploadMCPServiceIconMsg(serviceId=service_id, url=url),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.post("/{serviceId}", response_model=ActiveMCPServiceRsp)
async def active_or_deactivate_mcp_service(
        user_sub: Annotated[str, Depends(get_user)],
        service_id: Annotated[str, Path(..., alias="serviceId", description="服务ID")],
        data: ActiveMCPServiceRequest,
) -> JSONResponse:
    """激活/取消激活mcp"""
    try:
        if data.active:
            await MCPServiceManager.active_mcpservice(user_sub, service_id, data.mcp_env)
        else:
            await MCPServiceManager.deactive_mcpservice(user_sub, service_id)
    except Exception as e:
        err = f"[MCPService] 激活mcp服务失败: {e!s}" if data.active else f"[MCPService] 取消激活mcp服务失败: {e!s}"
        logger.exception(err)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=err,
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ActiveMCPServiceRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=BaseMCPServiceOperationMsg(serviceId=service_id),
        ).model_dump(exclude_none=True, by_alias=True),
    )
