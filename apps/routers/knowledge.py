# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 用户资产库路由"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import JSONResponse

from apps.dependency import get_user, verify_user
from apps.schemas.request_data import (
    UpdateKbReq,
)
from apps.schemas.response_data import (
    ListTeamKnowledgeMsg,
    ListTeamKnowledgeRsp,
    ResponseData,
)
from apps.services.knowledge import KnowledgeBaseManager

router = APIRouter(
    prefix="/api/knowledge",
    tags=["knowledge"],
    dependencies=[
        Depends(verify_user),
    ],
)


@router.get("", response_model=ListTeamKnowledgeRsp, responses={
    status.HTTP_404_NOT_FOUND: {"model": ResponseData},
},
)
async def list_kb(
    user_sub: Annotated[str, Depends(get_user)],
    conversation_id: Annotated[str, Query(alias="conversationId")],
    kb_id: Annotated[str, Query(alias="kbId")] = None,
    kb_name: Annotated[str, Query(alias="kbName")] = "",
) -> JSONResponse:
    """获取当前用户的知识库ID"""
    team_kb_list = await KnowledgeBaseManager.list_team_kb(user_sub, conversation_id, kb_id, kb_name)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ListTeamKnowledgeRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=ListTeamKnowledgeMsg(teamKbList=team_kb_list),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.put("", response_model=ResponseData)
async def update_conversation_kb(
    user_sub: Annotated[str, Depends(get_user)],
    conversation_id: Annotated[str, Query(alias="conversationId")],
    put_body: Annotated[UpdateKbReq, Body(...)],
) -> JSONResponse:
    """更新当前用户的知识库ID"""
    kb_ids_update_success = await KnowledgeBaseManager.update_conv_kb(user_sub, conversation_id, put_body.kb_ids)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=kb_ids_update_success,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.get("/team", response_model=ResponseData, responses={
    status.HTTP_404_NOT_FOUND: {"model": ResponseData},
})
async def list_team_kb(
    user_sub: Annotated[str, Depends(get_user)],
    kb_id: Annotated[str, Query(alias="kbId")] = None,
    kb_name: Annotated[str, Query(alias="kbName")] = "",
) -> JSONResponse:
    """获取团队知识库列表"""
    team_kb_list = await KnowledgeBaseManager.get_team_kb_list_from_rag(user_sub, kb_id, kb_name)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=team_kb_list,
        ).model_dump(exclude_none=True, by_alias=True),
    )
