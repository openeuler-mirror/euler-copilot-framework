# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI Flow拓扑结构展示API"""

from typing import Annotated
import logging

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import JSONResponse

from apps.dependency import get_user
from apps.dependency.user import verify_user
from apps.schemas.request_data import PutFlowReq
from apps.schemas.response_data import (
    FlowStructureDeleteMsg,
    FlowStructureDeleteRsp,
    FlowStructureGetMsg,
    FlowStructureGetRsp,
    FlowStructurePutMsg,
    FlowStructurePutRsp,
    NodeServiceListMsg,
    NodeServiceListRsp,
    ResponseData,
)
from apps.services.appcenter import AppCenterManager
from apps.services.application import AppManager
from apps.services.flow import FlowManager
from apps.services.flow_validate import FlowService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/flow",
    tags=["flow"],
    dependencies=[
        Depends(verify_user),
    ],
)


@router.get(
    "/service",
    responses={
        status.HTTP_200_OK: {"model": NodeServiceListRsp},
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def get_services(
    user_sub: Annotated[str, Depends(get_user)],
) -> NodeServiceListRsp:
    """获取用户可访问的节点元数据所在服务的信息"""
    services = await FlowManager.get_service_by_user_id(user_sub)
    if services is None:
        return NodeServiceListRsp(
            code=status.HTTP_404_NOT_FOUND,
            message="未找到符合条件的服务",
            result=NodeServiceListMsg(),
        )

    return NodeServiceListRsp(
        code=status.HTTP_200_OK,
        message="节点元数据所在服务信息获取成功",
        result=NodeServiceListMsg(services=services),
    )


@router.get(
    "",
    response_model=FlowStructureGetRsp,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ResponseData},
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def get_flow(
    user_sub: Annotated[str, Depends(get_user)],
    app_id: Annotated[str, Query(alias="appId")],
    flow_id: Annotated[str, Query(alias="flowId")],
) -> JSONResponse:
    """获取流拓扑结构"""
    if not await AppManager.validate_user_app_access(user_sub, app_id):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=FlowStructureGetRsp(
                code=status.HTTP_403_FORBIDDEN,
                message="用户没有权限访问该流",
                result=FlowStructureGetMsg(),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    result = await FlowManager.get_flow_by_app_and_flow_id(app_id, flow_id)
    if result is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=FlowStructureGetRsp(
                code=status.HTTP_404_NOT_FOUND,
                message="应用下流程获取失败",
                result=FlowStructureGetMsg(),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=FlowStructureGetRsp(
            code=status.HTTP_200_OK,
            message="应用下流程获取成功",
            result=FlowStructureGetMsg(flow=result),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.put(
    "",
    response_model=FlowStructurePutRsp,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ResponseData},
        status.HTTP_403_FORBIDDEN: {"model": ResponseData},
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ResponseData},
    },
)
async def put_flow(
    user_sub: Annotated[str, Depends(get_user)],
    app_id: Annotated[str, Query(alias="appId")],
    flow_id: Annotated[str, Query(alias="flowId")],
    put_body: Annotated[PutFlowReq, Body(...)],
) -> JSONResponse:
    """修改流拓扑结构"""
    if not await AppManager.validate_app_belong_to_user(user_sub, app_id):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=FlowStructurePutRsp(
                code=status.HTTP_403_FORBIDDEN,
                message="用户没有权限访问该流",
                result=FlowStructurePutMsg(),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    put_body.flow = await FlowService.remove_excess_structure_from_flow(put_body.flow)
    logger.error(f'{put_body.flow}')
    await FlowService.validate_flow_illegal(put_body.flow)
    logger.error(f'{put_body.flow}')
    put_body.flow.connectivity = await FlowService.validate_flow_connectivity(put_body.flow)
    logger.error(f'{put_body.flow}')
    result = await FlowManager.put_flow_by_app_and_flow_id(app_id, flow_id, put_body.flow)
    if result is None:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=FlowStructurePutRsp(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="应用下流更新失败",
                result=FlowStructurePutMsg(),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    flow = await FlowManager.get_flow_by_app_and_flow_id(app_id, flow_id)
    await AppCenterManager.update_app_publish_status(app_id, user_sub)
    if flow is None:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=FlowStructurePutRsp(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="应用下流更新后获取失败",
                result=FlowStructurePutMsg(),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=FlowStructurePutRsp(
            code=status.HTTP_200_OK,
            message="应用下流更新成功",
            result=FlowStructurePutMsg(flow=flow),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.delete(
    "",
    response_model=FlowStructureDeleteRsp,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def delete_flow(
    user_sub: Annotated[str, Depends(get_user)],
    app_id: Annotated[str, Query(alias="appId")],
    flow_id: Annotated[str, Query(alias="flowId")],
) -> JSONResponse:
    """删除流拓扑结构"""
    if not await AppManager.validate_app_belong_to_user(user_sub, app_id):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=FlowStructureDeleteRsp(
                code=status.HTTP_403_FORBIDDEN,
                message="用户没有权限访问该流",
                result=FlowStructureDeleteMsg(),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    result = await FlowManager.delete_flow_by_app_and_flow_id(app_id, flow_id)
    if result is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=FlowStructureDeleteRsp(
                code=status.HTTP_404_NOT_FOUND,
                message="应用下流程删除失败",
                result=FlowStructureDeleteMsg(),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=FlowStructureDeleteRsp(
            code=status.HTTP_200_OK,
            message="应用下流程删除成功",
            result=FlowStructureDeleteMsg(flowId=result),
        ).model_dump(exclude_none=True, by_alias=True),
    )
