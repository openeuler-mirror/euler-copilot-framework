# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 大模型相关接口"""

from typing import cast

from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from apps.dependency import verify_admin, verify_personal_token
from apps.schemas.request_data import (
    UpdateLLMReq,
    UpdateSpecialLlmReq,
)
from apps.schemas.response_data import (
    ListLLMAdminRsp,
    ListLLMRsp,
    LLMAdminInfo,
    LLMProviderInfo,
    ResponseData,
)
from apps.services.llm import LLMManager
from apps.services.settings import SettingsManager

router = APIRouter(
    prefix="/api/llm",
    tags=["llm"],
    dependencies=[
        Depends(verify_personal_token),
    ],
)
admin_router = APIRouter(
    prefix="/api/llm",
    tags=["llm"],
    dependencies=[
        Depends(verify_personal_token),
        Depends(verify_admin),
    ],
)


@router.get("/provider", response_model=ListLLMRsp,
    responses={status.HTTP_404_NOT_FOUND: {"model": ResponseData}},
)
async def list_llm(llmId: str | None = None) -> JSONResponse:  # noqa: N803
    """GET /llm: 获取大模型列表"""
    llm_list_raw = await LLMManager.list_llm(llmId, admin_view=False)

    # 检查返回类型是否符合预期
    if llm_list_raw and not all(isinstance(item, LLMProviderInfo) for item in llm_list_raw):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="大模型列表数据类型不符合预期",
                    result=None,
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )

    llm_list = cast("list[LLMProviderInfo]", llm_list_raw)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ListLLMRsp(
                code=status.HTTP_200_OK,
                message="success",
                result=llm_list,
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@admin_router.get("/config", response_model=ResponseData,
    responses={status.HTTP_404_NOT_FOUND: {"model": ResponseData}},
)
async def get_llm_config(llmId: str) -> JSONResponse:  # noqa: N803
    """GET /llm/config: 获取单个大模型的详细配置信息（管理员视图）"""
    llm = await LLMManager.get_llm(llmId)

    if not llm:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_404_NOT_FOUND,
                    message=f"大模型 {llmId} 不存在",
                    result=None,
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )

    llm_config = LLMAdminInfo(
        llmId=llm.id,
        llmDescription=llm.llmDescription,
        llmType=llm.llmType,
        baseUrl=llm.baseUrl,
        apiKey=llm.apiKey,
        modelName=llm.modelName,
        maxTokens=llm.maxToken,
        ctxLength=llm.ctxLength,
        temperature=llm.temperature,
        provider=llm.provider.value if llm.provider else None,
        extraConfig=llm.extraConfig,
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ListLLMAdminRsp(
                code=status.HTTP_200_OK,
                message="success",
                result=llm_config,
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )

@admin_router.put("/setting", response_model=ResponseData,
    responses={status.HTTP_404_NOT_FOUND: {"model": ResponseData}},
)
async def change_global_llm(request: Request, req: UpdateSpecialLlmReq) -> JSONResponse:
    """PUT /llm/setting: 更改全局Function和Embedding模型设置（管理员）"""
    try:
        user_id = request.state.user_id

        await SettingsManager.update_global_llm_settings(user_id, req)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_200_OK,
                    message="success",
                    result={
                        "functionLLM": req.functionLLM,
                        "embeddingLLM": req.embeddingLLM,
                    },
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message=str(e),
                    result=None,
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )


@admin_router.put("",
    responses={status.HTTP_404_NOT_FOUND: {"model": ResponseData}},
)
async def create_llm(req: UpdateLLMReq) -> JSONResponse:
    """PUT /llm: 创建或更新大模型配置"""
    try:
        await LLMManager.update_llm(req.llm_id, req)
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message=str(e),
                    result=None,
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ResponseData(
                code=status.HTTP_200_OK,
                message="success",
                result=req.llm_id,
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@admin_router.delete("",
    responses={status.HTTP_404_NOT_FOUND: {"model": ResponseData}},
)
async def delete_llm(llmId: str) -> JSONResponse:  # noqa: N803
    """DELETE /llm: 删除大模型配置"""
    try:
        await LLMManager.delete_llm(llmId)
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message=str(e),
                    result=None,
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ResponseData(
                code=status.HTTP_200_OK,
                message="success",
                result=llmId,
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )
