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
    model_type: Annotated[str | None, Query(description="模型类型", alias="modelType")] = None,
) -> JSONResponse:
    """获取大模型列表"""
    llm_list = await LLMManager.list_llm(user_sub, llm_id, model_type)
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
    llm_id: Annotated[str, Query(description="llm ID", alias="llmId")] = "",
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
async def get_embedding_config(
    user_sub: Annotated[str, Depends(get_user)]
) -> JSONResponse:
    """获取 Embedding 模型列表"""
    # 使用单一查询获取用户可访问的所有embedding模型
    all_models = await LLMManager.list_all_embedding_models(user_sub)
    
    # 为了兼容原有接口，返回第一个模型的配置
    if all_models:
        first_model = all_models[0]
        embedding_config = {
            'llmId': first_model.llm_id,
            'type': 'embedding',
            'endpoint': first_model.openai_base_url,
            'api_key': first_model.openai_api_key,
            'model': first_model.model_name,
            'icon': first_model.icon,
        }
    else:
        # 如果没有模型，使用配置文件的默认值
        config = Config().get_config()
        embedding_config = {
            'type': 'embedding',
            'endpoint': config.embedding.endpoint,
            'api_key': config.embedding.api_key,
            'model': config.embedding.model,
            'icon': config.embedding.icon,
        }
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=embedding_config,
        ).model_dump(exclude_none=True, by_alias=True),
    )

@router.get("/reranker", response_model=ResponseData)
async def get_reranker_config(
    user_sub: Annotated[str, Depends(get_user)]
) -> JSONResponse:
    """获取 Reranker 模型列表"""
    # 使用单一查询获取用户可访问的所有reranker模型
    all_models = await LLMManager.list_all_reranker_models(user_sub)
    
    result = []
    
    # 添加算法类型reranker
    result.append({
        'type': 'algorithm',
        'name': 'jaccard_dis_reranker',
        'llmId': 'algorithm_jaccard',
        'modelName': 'Jaccard Distance Reranker',
        'icon': ''
    })
    
    # 添加数据库中的reranker模型
    for model in all_models:
        result.append({
            'type': 'reranker',
            'llmId': model.llm_id,
            'modelName': model.model_name,
            'icon': model.icon,
            'endpoint': model.openai_base_url,
            'apiKey': model.openai_api_key,
            'model': model.model_name
        })
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=result,
        ).model_dump(exclude_none=True, by_alias=True),
    )