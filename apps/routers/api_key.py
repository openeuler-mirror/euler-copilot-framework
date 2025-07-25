# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI API Key相关路由"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse


from apps.dependency.user import get_user, verify_user
from apps.schemas.api_key import GetAuthKeyRsp, PostAuthKeyMsg, PostAuthKeyRsp
from apps.schemas.response_data import ResponseData
from apps.services.api_key import ApiKeyManager

router = APIRouter(
    prefix="/api/auth/key",
    tags=["key"],
    dependencies=[Depends(verify_user)],
)


@router.get("", response_model=GetAuthKeyRsp)
async def check_api_key_existence(user_sub: Annotated[str, Depends(get_user)]) -> JSONResponse:
    """检查API密钥是否存在"""
    exists: bool = await ApiKeyManager.api_key_exists(user_sub)
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="success",
        result={
            "api_key_exists": exists,
        },
    ).model_dump(exclude_none=True, by_alias=True))


@router.post("", responses={
    400: {"model": ResponseData},
}, response_model=PostAuthKeyRsp)
async def manage_api_key(action: str, user_sub: Annotated[str, Depends(get_user)]) -> JSONResponse:
    """管理用户的API密钥"""
    action = action.lower()
    if action == "create":
        api_key: str | None = await ApiKeyManager.generate_api_key(user_sub)
    elif action == "update":
        api_key: str | None = await ApiKeyManager.update_api_key(user_sub)
    elif action == "delete":
        success: bool = await ApiKeyManager.delete_api_key(user_sub)
        if success:
            return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
                code=status.HTTP_200_OK,
                message="success",
                result={},
            ).model_dump(exclude_none=True, by_alias=True))
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=ResponseData(
            code=status.HTTP_400_BAD_REQUEST,
            message="failed to revoke api key",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    else:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=ResponseData(
            code=status.HTTP_400_BAD_REQUEST,
            message="invalid request",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))

    if api_key is None:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=ResponseData(
            code=status.HTTP_400_BAD_REQUEST,
            message="failed to generate api key",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=PostAuthKeyRsp(
        code=status.HTTP_200_OK,
        message="success",
        result=PostAuthKeyMsg(
            api_key=api_key,
        ),
    ).model_dump(exclude_none=True, by_alias=True))
