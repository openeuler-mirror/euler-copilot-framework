"""FastAPI 用户画像相关API

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from apps.dependency.csrf import verify_csrf_token
from apps.dependency.user import verify_user
from apps.entities.request_data import PostDomainData
from apps.entities.response_data import ResponseData
from apps.manager.domain import DomainManager

router = APIRouter(
    prefix="/api/domain",
    tags=["domain"],
    dependencies=[
        Depends(verify_csrf_token),
        Depends(verify_user),
    ],
)


@router.post("", response_model=ResponseData)
async def add_domain(post_body: PostDomainData):  # noqa: ANN201
    """添加用户领域画像"""
    if await DomainManager.get_domain_by_domain_name(post_body.domain_name):
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="add domain name is exist.",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))

    if not await DomainManager.add_domain(post_body):
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="add domain failed",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="add domain success.",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))


@router.put("", response_model=ResponseData)
async def update_domain(post_body: PostDomainData):  # noqa: ANN201
    """更新用户领域画像"""
    if not await DomainManager.get_domain_by_domain_name(post_body.domain_name):
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="update domain name is not exist.",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    if not await DomainManager.update_domain_by_domain_name(post_body):
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="update domain failed",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="update domain success.",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))


@router.delete("", response_model=ResponseData)
async def delete_domain(post_body: PostDomainData):  # noqa: ANN201
    """删除用户领域画像"""
    if not await DomainManager.get_domain_by_domain_name(post_body.domain_name):
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="delete domain name is not exist.",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    if not await DomainManager.delete_domain_by_domain_name(post_body):
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="delete domain failed",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="delete domain success.",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))
