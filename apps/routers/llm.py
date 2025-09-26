# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 大模型相关接口"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from apps.common.config import Config
from apps.dependency import get_user, verify_user
from apps.schemas.request_data import (
    UpdateLLMReq,
)
from apps.schemas.response_data import (
    ListLLMProviderRsp,
    ListLLMRsp,
    ResponseData,
)
from apps.services.llm import LLMManager

router = APIRouter(
    prefix="/api/llm",
    tags=["llm"],
    dependencies=[
        Depends(verify_user),
    ],
)


@router.get("/provider", response_model=ListLLMProviderRsp, responses={
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def list_llm_provider() -> JSONResponse:
    """获取大模型提供商列表"""
    llm_provider_list = await LLMManager.list_llm_provider()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ListLLMProviderRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=llm_provider_list,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.get(
    "", response_model=ListLLMRsp,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def list_llm(
    user_sub: Annotated[str, Depends(get_user)],
    llm_id: Annotated[str | None, Query(description="大模型ID", alias="llmId")] = None,
) -> JSONResponse:
    """获取大模型列表"""
    llm_list = await LLMManager.list_llm(user_sub, llm_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ListLLMRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=llm_list,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.put(
    "",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def create_llm(
    req: UpdateLLMReq,
    user_sub: Annotated[str, Depends(get_user)],
    llm_id: Annotated[str | None, Query(description="大模型ID", alias="llmId")] = None,
) -> JSONResponse:
    """创建或更新大模型配置"""
    llm_id = await LLMManager.update_llm(user_sub, llm_id, req)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=llm_id,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.delete(
    "",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def delete_llm(
    user_sub: Annotated[str, Depends(get_user)],
    llm_id: Annotated[str, Query(description="大模型ID", alias="llmId")],
) -> JSONResponse:
    """删除大模型配置"""
    llm_id = await LLMManager.delete_llm(user_sub, llm_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=llm_id,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.put(
    "/conv",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def update_conv_llm(
    user_sub: Annotated[str, Depends(get_user)],
    conversation_id: Annotated[str, Query(description="对话ID", alias="conversationId")],
    llm_id: Annotated[str, Query(description="llm ID", alias="llmId")] = "empty",
) -> JSONResponse:
    """更新对话的知识库"""
    llm_id = await LLMManager.update_conversation_llm(user_sub, conversation_id, llm_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=llm_id,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.get("/embedding", response_model=ResponseData)
async def get_embedding_config() -> JSONResponse:
    """获取 Embedding 配置"""
    config = Config().get_config()
    embedding_config = config.embedding.__dict__
    
    # 如果配置中没有 icon，添加一个默认图标
    if 'icon' not in embedding_config or not embedding_config['icon']:
        # 根据模型名称设置默认图标
        model_name = embedding_config.get('model', '')
        if 'bge' in model_name.lower() and 'baai' in model_name.lower():
            embedding_config['icon'] = 'https://sf-maas-uat-prod.oss-cn-shanghai.aliyuncs.com/Model_LOGO/BAAI.svg'
        else:
            embedding_config['icon'] = ''
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=embedding_config,
        ).model_dump(exclude_none=True, by_alias=True),
    )

@router.get("/reranker", response_model=ResponseData)
async def get_reranker_config() -> JSONResponse:
    """获取 Reranker 配置"""
    config = Config().get_config()
    reranker_config = config.reranker.__dict__
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=[
                {
                    'type': 'algorithm',
                    'name': 'jaccard_dis_reranker'
                },
                reranker_config
            ],
        ).model_dump(exclude_none=True, by_alias=True),
    )