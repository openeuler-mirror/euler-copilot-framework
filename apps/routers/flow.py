"""FastAPI 用户画像相关API

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from fastapi import APIRouter, Depends, status,Path,Query,Body
from fastapi.responses import JSONResponse

from apps.dependency.csrf import verify_csrf_token
from apps.dependency.user import verify_user
from apps.entities.request_data import PutFlowReq,PutNodeParameterReq
from apps.entities.response_data import NodeMetaDataListRsp,FlowStructureGetRsp,FlowStructurePutRsp,\
    FlowStructureDeleteRsp,NodeParameterGetRsp,NodeParameterListRsp,NodeParameterPutRsp
from apps.manager.domain import DomainManager

router = APIRouter(
    prefix="/api/flow",
    tags=["flow"],
    dependencies=[
        Depends(verify_csrf_token),
        Depends(verify_user),
    ],
)


@router.get("/node/metadata",response_model=NodeMetaDataListRsp)
async def get_node_metadatas(page:int =Query(...),
                            page_size:int =Query(...,alias="pageSize")):  # noqa: ANN201
    """获取节点元数据"""
    pass

@router.get("/{flowId}", response_model=FlowStructureGetRsp)
async def get_flow(flowId: str = Path(..., title="流的id")):
    flow_id=flowId
    pass

@router.put("", response_model=FlowStructurePutRsp)
async def put_flow(flow_id:str = Query(..., alias="flowId"),
                   put_body: PutFlowReq=Body(...)):
    pass

@router.delete("/{flowId}", response_model=FlowStructureDeleteRsp)
async def delte_flow(flowId: str = Path(..., title="流的id")):
    flow_id=flowId
    pass

@router.get("/node/parameter", response_model=NodeParameterGetRsp)
async def get_node_parameter(flow_id:str = Query(..., alias="flowId"),
                             node_id:str = Query(..., alias="nodeId")):
    pass
@router.get("/node/parameter/history", response_model=NodeParameterListRsp)
async def get_node_parameter_history(flow_id:str = Query(..., alias="flowId"),
                                     node_id:str = Query(..., alias="nodeId"),
                                     start_time:str = Query(..., alias="startTime"),
                                     end_time:str = Query(..., alias="endTime"),
                                     page:int =Query(...),
                                     page_size:int =Query(...,alias="pageSize"),
                                     ):
    pass
@router.put("/node/parameter", response_model=NodeParameterPutRsp)
async def put_node_parameter(flow_id:str = Query(..., alias="flowId"),
                            node_id:str = Query(..., alias="nodeId"),
                            put_body:PutNodeParameterReq=Body(...)):
    pass

