"""FastAPI Flow拓扑结构展示API

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from fastapi import APIRouter, Depends, status, Path, Query, Body
from fastapi.responses import JSONResponse
from typing import Annotated, Optional

from apps.dependency.csrf import verify_csrf_token
from apps.dependency.user import verify_user
from apps.dependency import get_user
from apps.entities.request_data import PutFlowReq
from apps.entities.response_data import NodeServiceListRsp, NodeServiceListMsg, NodeMetaDataListRsp, NodeMetaDataListMsg, FlowStructureGetRsp, \
    FlowStructureGetMsg, FlowStructurePutRsp, FlowStructurePutMsg, FlowStructureDeleteRsp, FlowStructureDeleteMsg, ResponseData
from apps.manager.flow import FlowManager
from apps.manager.application import AppManager
from apps.utils.flow import FlowService
router = APIRouter(
    prefix="/api/flow",
    tags=["flow"],
    dependencies=[
        Depends(verify_csrf_token),
        Depends(verify_user),
    ],
)


@router.get("/service", response_model=NodeMetaDataListRsp, responses={
    status.HTTP_404_NOT_FOUND: {"model": ResponseData},
})
async def get_node_metadatas(
    user_sub: Annotated[str, Depends(get_user)],
    page: int = Query(...),
    page_size: int = Query(..., alias="pageSize"),
):
    """获取用户可访问的节点元数据所在服务的信息"""
    result = await FlowManager.get_node_meta_datas_by_service_id(user_sub, page, page_size)
    if result is None:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=ResponseData(
            code=status.HTTP_404_NOT_FOUND,
            message="节点元数据所在服务信息不存在",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=NodeServiceListRsp(
        code=status.HTTP_200_OK,
        message="节点元数据所在服务信息获取成功",
        result=NodeServiceListMsg(total=result[0], services=result[1])
    ).model_dump(exclude_none=True, by_alias=True))


@router.get("/service/node", response_model=NodeMetaDataListRsp, responses={
    status.HTTP_403_FORBIDDEN: {"model": ResponseData},
    status.HTTP_404_NOT_FOUND: {"model": ResponseData}
})
async def get_flow(
    user_sub: Annotated[str, Depends(get_user)],
    service_id: int = Query(..., alias="serviceId")
):
    """获取用户可访问的节点元数据"""
    if not await AppManager.validate_user_app_access(user_sub, service_id):
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=ResponseData(
            code=status.HTTP_403_FORBIDDEN,
            message="用户没有权限访问该服务",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))

    result = await FlowManager.get_node_meta_datas_by_service_id(service_id)
    if result is None:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=ResponseData(
            code=status.HTTP_404_NOT_FOUND,
            message="服务下节点元数据获取失败",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=NodeMetaDataListRsp(
        code=status.HTTP_200_OK,
        message="服务下节点元数据获取成功",
        result=NodeMetaDataListMsg(node_meta_datas=result)
    ).model_dump(exclude_none=True, by_alias=True))


@router.get("", response_model=FlowStructureGetRsp, responses={
    status.HTTP_403_FORBIDDEN: {"model": ResponseData},
    status.HTTP_404_NOT_FOUND: {"model": ResponseData}
})
async def get_flow(
        user_sub: Annotated[str, Depends(get_user)],
        app_id: str = Query(..., alias="appId"),
        flow_id: str = Query(..., alias="flowId")
):
    """获取流拓扑结构"""
    if not await AppManager.validate_user_app_access(user_sub, app_id):
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=ResponseData(
            code=status.HTTP_403_FORBIDDEN,
            message="用户没有权限访问该流",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    result = await FlowManager.get_flow_by_app_and_flow_id(app_id, flow_id)
    if result is None:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=ResponseData(
            code=status.HTTP_404_NOT_FOUND,
            message="应用下流程获取失败",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=FlowStructureGetRsp(
        code=status.HTTP_200_OK,
        message="应用下流程获取成功",
        result=FlowStructureGetMsg(flow=result[0], focus_point=result[1])
    ).model_dump(exclude_none=True, by_alias=True))


@router.put("", response_model=FlowStructurePutRsp, responses={
    status.HTTP_400_BAD_REQUEST: {"model": ResponseData},
    status.HTTP_403_FORBIDDEN: {"model": ResponseData},
    status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ResponseData}
})
async def put_flow(
    user_sub: Annotated[str, Depends(get_user)],
    app_id: str = Query(..., alias="appId"),
    flow_id: str = Query(..., alias="flowId"),
    topology_check: Optional[bool] = Query(..., alias="topologyCheck"),
    put_body: PutFlowReq = Body(...)
):
    """修改流拓扑结构"""
    if not await AppManager.validate_user_app_access(user_sub, app_id):
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=ResponseData(
            code=status.HTTP_403_FORBIDDEN,
            message="用户没有权限访问该流",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    if topology_check:
        await FlowService.validate_flow_connectivity(put_body.flow)
    await FlowService.validate_flow_illegal(put_body.flow)
    result = await FlowManager.put_flow_by_app_and_flow_id(app_id, flow_id, put_body.flow, put_body.focus_point)
    if result is None:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="应用下流程更新失败",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=FlowStructurePutRsp(
        code=status.HTTP_200_OK,
        message="应用下流程更新成功",
        result=FlowStructurePutMsg(flow_id=result)
    ).model_dump(exclude_none=True, by_alias=True))


@router.delete("", response_model=FlowStructureDeleteRsp, responses={
    status.HTTP_404_NOT_FOUND: {"model": ResponseData}
})
async def delete_flow(
    user_sub: Annotated[str, Depends(get_user)],
    app_id: str = Query(..., alias="appId"),
    flow_id: str = Query(..., alias="flowId")
):
    """删除流拓扑结构"""
    if not await AppManager.validate_user_app_access(user_sub, app_id):
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=ResponseData(
            code=status.HTTP_403_FORBIDDEN,
            message="用户没有权限访问该流",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    result = await FlowManager.delete_flow_by_app_and_flow_id(app_id, flow_id)
    if result is None:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=ResponseData(
            code=status.HTTP_404_NOT_FOUND,
            message="应用下流程删除失败",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=FlowStructureDeleteRsp(
        code=status.HTTP_200_OK,
        message="应用下流程删除成功",
        result=FlowStructureDeleteMsg(flow_id=result)
    ).model_dump(exclude_none=True, by_alias=True))
