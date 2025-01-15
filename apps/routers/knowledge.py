"""FastAPI 用户资产库路由

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from apps.dependency import get_user, verify_user
from apps.entities.request_data import (
    PostKnowledgeIDData,
)
from apps.entities.response_data import (
    GetKnowledgeIDMsg,
    GetKnowledgeIDRsp,
    ResponseData,
)
from apps.manager.knowledge import KnowledgeBaseManager

router = APIRouter(
    prefix="/api/knowledge",
    tags=["知识库"],
    dependencies=[
        Depends(verify_user),
    ],
)


@router.get("", response_model=GetKnowledgeIDRsp, responses={
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def get_kb_id(user_sub: Annotated[str, Depends(get_user)]):  # noqa: ANN201
    """获取当前用户的知识库ID"""
    kb_id = await KnowledgeBaseManager.get_kb_id(user_sub)
    kb_id_str = "" if kb_id is None else kb_id
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=GetKnowledgeIDRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=GetKnowledgeIDMsg(kb_id=kb_id_str),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.post("", response_model=ResponseData)
async def change_kb_id(post_body: PostKnowledgeIDData, user_sub: Annotated[str, Depends(get_user)]):  # noqa: ANN201
    """修改当前用户的知识库ID"""
    result = await KnowledgeBaseManager.change_kb_id(user_sub, post_body.kb_id)
    if not result:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="change kb_id error",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result={},
        ).model_dump(exclude_none=True, by_alias=True),
    )

