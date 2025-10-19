# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户相关接口"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, status, Query
from fastapi.responses import JSONResponse

from apps.dependency import get_user
from apps.schemas.request_data import UserUpdateRequest, UserPreferencesRequest
from apps.schemas.response_data import UserGetMsp, UserGetRsp
from apps.schemas.user import UserInfo
from apps.services.user import UserManager

router = APIRouter(
    prefix="/api/user",
    tags=["user"],
)


@router.get("", response_model=UserGetRsp)
async def get_user_sub(
    user_sub: Annotated[str, Depends(get_user)],
    page_size: Annotated[int, Query(description="每页用户数量")] = 20,
    page_cnt: Annotated[int, Query(description="当前页码")] = 1,
) -> JSONResponse:
    """查询所有用户接口"""
    user_list, total = await UserManager.get_all_user_sub(page_cnt=page_cnt, page_size=page_size, filter_user_subs=[user_sub])
    user_info_list = []
    for user in user_list:
        if user == user_sub:
            continue
        # 获取用户详细信息，包括用户名
        user_info = await UserManager.get_userinfo_by_user_sub(user)
        user_name = user_info.user_name if user_info and user_info.user_name else user
        
        info = UserInfo(
            userName=user_name,
            userSub=user,
        )
        user_info_list.append(info)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=UserGetRsp(
            code=status.HTTP_200_OK,
            message="用户数据详细信息获取成功",
            result=UserGetMsp(userInfoList=user_info_list, total=total),
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

    await UserManager.update_userinfo_by_user_sub(user_sub, data)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"code": status.HTTP_200_OK, "message": "用户信息更新成功"},
    )


@router.put("/preferences")
async def update_user_preferences(
    user_sub: Annotated[str, Depends(get_user)],
    *,
    data: Annotated[UserPreferencesRequest, Body(..., description="用户偏好设置更新信息")],
) -> JSONResponse:
    """更新用户偏好设置接口"""
    await UserManager.update_user_preferences_by_user_sub(user_sub, data)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"code": status.HTTP_200_OK, "message": "用户偏好设置更新成功"},
    )


@router.get("/preferences")
async def get_user_preferences(
    user_sub: Annotated[str, Depends(get_user)],
) -> JSONResponse:
    """获取用户偏好设置接口"""
    preferences = await UserManager.get_user_preferences_by_user_sub(user_sub)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "code": status.HTTP_200_OK, 
            "message": "用户偏好设置获取成功",
            "result": preferences.model_dump(by_alias=True, exclude_none=True)
        },
    )
