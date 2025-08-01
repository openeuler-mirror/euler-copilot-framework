# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户相关接口"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, status
from fastapi.responses import JSONResponse

from apps.dependency import get_user
from apps.schemas.request_data import UserUpdateRequest
from apps.schemas.response_data import UserGetMsp, UserGetRsp
from apps.schemas.user import UserInfo
from apps.services.user import UserManager

router = APIRouter(
    prefix="/api/user",
    tags=["user"],
)


@router.get("")
async def get_user_sub(
    user_sub: Annotated[str, Depends(get_user)],
) -> JSONResponse:
    """查询所有用户接口"""
    user_list = await UserManager.get_all_user_sub()
    user_info_list = []
    for user in user_list:
        # user_info = await UserManager.get_userinfo_by_user_sub(user) 暂时不需要查询user_name
        if user == user_sub:
            continue
        info = UserInfo(
            userName=user,
            userSub=user,
        )
        user_info_list.append(info)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=UserGetRsp(
            code=status.HTTP_200_OK,
            message="用户数据详细信息获取成功",
            result=UserGetMsp(userInfoList=user_info_list),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.post("")
async def update_user_info(
    user_sub: Annotated[str, Depends(get_user)],
    *,
    data: Annotated[UserUpdateRequest, Body(..., description="用户更新信息")],
) -> JSONResponse:
    """更新用户信息接口"""
    # 更新用户信息

    result = await UserManager.update_userinfo_by_user_sub(user_sub, data)
    if not result:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"code": status.HTTP_200_OK, "message": "用户信息更新成功"},
        )
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"code": status.HTTP_404_NOT_FOUND, "message": "用户信息更新失败"},
    )
