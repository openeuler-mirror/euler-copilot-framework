# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户相关接口"""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from apps.dependency import verify_personal_token, verify_session
from apps.schemas.request_data import UserUpdateRequest
from apps.schemas.response_data import ResponseData
from apps.schemas.tag import UserTagListResponse
from apps.schemas.user import UserListItem, UserListMsg, UserListRsp
from apps.services.user import UserManager
from apps.services.user_tag import UserTagManager

router = APIRouter(
    prefix="/api/user",
    tags=["user"],
    dependencies=[Depends(verify_session), Depends(verify_personal_token)],
)


@router.post("", response_model=ResponseData)
async def update_user_info(request: Request, data: UserUpdateRequest) -> JSONResponse:
    """POST /api/user: 更新当前用户信息"""
    # 更新用户信息
    await UserManager.update_user(request.state.user_sub, data.model_dump(exclude_unset=True, exclude_none=True))

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"code": status.HTTP_200_OK, "message": "用户信息更新成功"},
    )


# TODO
@router.get("")
async def get_user_info(request: Request) -> JSONResponse:
    """GET /api/user/info: 获取当前用户信息"""
    user = await UserManager.get_user(request.state.user_sub)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(code=status.HTTP_200_OK, message="success", result=user),
    )


@router.get("/list")
async def list_user(
    request: Request, page_size: int = 10, page_num: int = 1,
) -> JSONResponse:
    """查询不包含当前用户的所有用户名，作为列表返回给前端。应用权限设置等时使用"""
    user_list, total = await UserManager.list_user(page_size, page_num)
    user_info_list = []
    for user in user_list:
        if user.userSub == request.state.user_sub:
            continue
        info = UserListItem(
            userName=user.userSub,
            userSub=user.userSub,
        )
        user_info_list.append(info)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=UserListRsp(
            code=status.HTTP_200_OK,
            message="用户数据详细信息获取成功",
            result=UserListMsg(userInfoList=user_info_list, total=total),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.get("/tag",
    responses={status.HTTP_404_NOT_FOUND: {"model": ResponseData}},
)
async def get_user_tag(
    request: Request,
    topk: int | None = None,
) -> JSONResponse:
    """GET /user/tag?topk=5: 获取用户标签"""
    try:
        tags = await UserTagManager.get_user_domain_by_user_and_topk(request.state.user_sub, topk)
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=str(e),
                result=None,
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=UserTagListResponse(tags=tags),
        ).model_dump(exclude_none=True, by_alias=True),
    )
