# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 用户标签相关API"""

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from apps.dependency.user import verify_admin, verify_personal_token, verify_session
from apps.schemas.request_data import PostTagData
from apps.schemas.response_data import ResponseData
from apps.services.tag import TagManager

admin_router = APIRouter(
    prefix="/api/tag",
    tags=["tag"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
        Depends(verify_admin),
    ],
)


@admin_router.get("")
async def get_user_tag() -> JSONResponse:
    """GET /tag: 获取所有标签"""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ResponseData(
                code=status.HTTP_200_OK,
                message="[Tag] Get all tag success.",
                result=await TagManager.get_all_tag(),
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@admin_router.post("", response_model=ResponseData)
async def update_tag(post_body: PostTagData) -> JSONResponse:
    """添加或改动特定标签定义"""
    if not await TagManager.update_tag_by_name(post_body):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="[Tag] Update tag failed",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ResponseData(
                code=status.HTTP_200_OK,
                message="[Tag] Update tag success.",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@admin_router.delete("", response_model=ResponseData)
async def delete_tag(post_body: PostTagData) -> JSONResponse:
    """删除某个标签"""
    if not await TagManager.get_tag_by_name(post_body.tag):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="[Tag] Tag does not exist.",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    try:
        await TagManager.delete_tag(post_body)
    except Exception as e:  # noqa: BLE001
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message=f"[Tag] Delete tag failed: {e!s}",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ResponseData(
                code=status.HTTP_200_OK,
                message="[Tag] Delete tag success.",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )
