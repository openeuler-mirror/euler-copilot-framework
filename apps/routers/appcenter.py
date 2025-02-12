"""FastAPI 应用中心相关路由

Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""
from typing import Annotated, Optional, Union

from fastapi import APIRouter, Body, Depends, Path, Query, status
from fastapi.requests import HTTPConnection
from fastapi.responses import JSONResponse

from apps.dependency.csrf import verify_csrf_token
from apps.dependency.user import get_user, verify_user
from apps.entities.appcenter import AppPermissionData
from apps.entities.enum_var import SearchType
from apps.entities.request_data import CreateAppRequest, ModFavAppRequest
from apps.entities.response_data import (
    BaseAppOperationMsg,
    BaseAppOperationRsp,
    GetAppListMsg,
    GetAppListRsp,
    GetAppPropertyMsg,
    GetAppPropertyRsp,
    GetRecentAppListRsp,
    ModFavAppMsg,
    ModFavAppRsp,
    ResponseData,
)
from apps.manager.appcenter import AppCenterManager
from apps.manager.flow import FlowManager

router = APIRouter(
    prefix="/api/app",
    tags=["appcenter"],
    dependencies=[Depends(verify_user)],
)


@router.get("", response_model=Union[GetAppListRsp, ResponseData])
async def get_applications(  # noqa: ANN201, PLR0913
    user_sub: Annotated[str, Depends(get_user)],
    *,
    my_app: Annotated[bool, Query(..., alias="createdByMe", description="筛选我创建的")] = False,
    my_fav: Annotated[bool, Query(..., alias="favorited", description="筛选我收藏的")] = False,
    search_type: Annotated[SearchType, Query(..., alias="searchType", description="搜索类型")] = SearchType.ALL,
    keyword: Annotated[Optional[str], Query(..., alias="keyword", description="搜索关键字")] = None,
    page: Annotated[int, Query(..., alias="page", ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(..., alias="pageSize", ge=1, le=100, description="每页条数")] = 20,
):
    """获取应用列表"""
    if my_app and my_fav:  # 只能同时使用一个过滤条件
        return ResponseData(
            code=status.HTTP_400_BAD_REQUEST,
            message="createdByMe 和 favorited 不能同时生效",
            result={},
        )

    app_cards, total_apps = [], -1
    if my_app:    # 筛选我创建的
        app_cards, total_apps = await AppCenterManager.fetch_user_apps(
            user_sub, search_type, keyword, page, page_size)
    elif my_fav:  # 筛选已收藏的
        app_cards, total_apps = await AppCenterManager.fetch_favorite_apps(
            user_sub, search_type, keyword, page, page_size)
    else:         # 获取所有应用
        app_cards, total_apps = await AppCenterManager.fetch_all_apps(
            user_sub, search_type, keyword, page, page_size)
    if total_apps == -1:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="查询失败",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=GetAppListRsp(
        code=status.HTTP_200_OK,
        message="查询成功",
        result=GetAppListMsg(
            currentPage=page,
            total=total_apps,
            applications=app_cards,
        ),
    ).model_dump(exclude_none=True, by_alias=True))


@router.post("", dependencies=[Depends(verify_csrf_token)], response_model=Union[BaseAppOperationRsp, ResponseData])
async def create_or_update_application(  # noqa: ANN201
    request: Annotated[CreateAppRequest, Body(...)],
    user_sub: Annotated[str, Depends(get_user)],
):
    """创建或更新应用"""
    app_id = request.app_id
    if app_id:
        # 更新应用
        confirm = await AppCenterManager.update_app(app_id, request)
        if not confirm:
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="更新失败",
                result={},
            ).model_dump(exclude_none=True, by_alias=True))
        return JSONResponse(status_code=status.HTTP_200_OK, content=BaseAppOperationRsp(
            code=status.HTTP_200_OK,
            message="更新成功",
            result=BaseAppOperationMsg(appId=app_id),
        ).model_dump(exclude_none=True, by_alias=True))
    # 创建应用
    app_id = await AppCenterManager.create_app(user_sub, request)
    if not app_id:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="创建失败",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=BaseAppOperationRsp(
        code=status.HTTP_200_OK,
        message="创建成功",
        result=BaseAppOperationMsg(appId=app_id),
    ).model_dump(exclude_none=True, by_alias=True))


@router.get("/recent", response_model=Union[GetRecentAppListRsp, ResponseData])
async def get_recently_used_applications(  # noqa: ANN201
    user_sub: Annotated[str, Depends(get_user)],
    count: Annotated[int, Query(..., ge=1, le=10)] = 5,
):
    """获取最近使用的应用"""
    recent_apps = await AppCenterManager.get_recently_used_apps(
        count, user_sub)
    if recent_apps is None:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="查询失败",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=GetRecentAppListRsp(
        code=status.HTTP_200_OK,
        message="查询成功",
        result=recent_apps,
    ).model_dump(exclude_none=True, by_alias=True))


@router.get("/{appId}", response_model=Union[GetAppPropertyRsp, ResponseData])
async def get_application(  # noqa: ANN201
    app_id: Annotated[str, Path(..., alias="appId", description="应用ID")],
):
    """获取应用详情"""
    app_data = await AppCenterManager.fetch_app_data_by_id(app_id)
    if not app_data:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=ResponseData(
            code=status.HTTP_404_NOT_FOUND,
            message="找不到应用",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    workflows = [{"id":flow.id,"name":flow.name} for flow in app_data.flows]
    return JSONResponse(status_code=status.HTTP_200_OK, content=GetAppPropertyRsp(
        code=status.HTTP_200_OK,
        message="查询成功",
        result=GetAppPropertyMsg(
            appId=app_data.id,
            published=app_data.published,
            name=app_data.name,
            description=app_data.description,
            icon=app_data.icon,
            links=app_data.links,
            recommendedQuestions=app_data.first_questions,
            dialogRounds=app_data.history_len,
            permission=AppPermissionData(
                visibility=app_data.permission.type,
                authorizedUsers=app_data.permission.users,
            ),
            workflows=workflows,
        ),
    ).model_dump(exclude_none=True, by_alias=True))


@router.delete(
    "/{appId}",
    dependencies=[Depends(verify_csrf_token)],
    response_model=Union[BaseAppOperationRsp, ResponseData],
)
async def delete_application(  # noqa: ANN201
    app_id: Annotated[str, Path(..., alias="appId", description="应用ID")],
    user_sub: Annotated[str, Depends(get_user)],
):
    """删除应用"""
    app_data = await AppCenterManager.fetch_app_data_by_id(app_id)
    if not app_data:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=ResponseData(
            code=status.HTTP_400_BAD_REQUEST,
            message="查询失败",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    # 校验应用作者是否为当前用户
    if app_data.author != user_sub:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=ResponseData(
            code=status.HTTP_403_FORBIDDEN,
            message="无权删除他人创建的应用",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    # 删除应用相关的工作流
    for flow in app_data.flows:
        if not await FlowManager.delete_flow_by_app_and_flow_id(app_id, flow.id):
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"删除应用下属工作流 {flow.id} 失败",
                result={},
            ).model_dump(exclude_none=True, by_alias=True))
    # 删除应用
    if not await AppCenterManager.delete_app(app_id, user_sub):
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="删除失败",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=BaseAppOperationRsp(
        code=status.HTTP_200_OK,
        message="删除成功",
        result=BaseAppOperationMsg(appId=app_id),
    ).model_dump(exclude_none=True, by_alias=True))


@router.post("/{appId}", dependencies=[Depends(verify_csrf_token)], response_model=BaseAppOperationRsp)
async def publish_application(  # noqa: ANN201
    app_id: Annotated[str, Path(..., alias="appId", description="应用ID")],
    user_sub: Annotated[str, Depends(get_user)],
):
    """发布应用"""
    app_data = await AppCenterManager.fetch_app_data_by_id(app_id)
    if not app_data:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=ResponseData(
            code=status.HTTP_400_BAD_REQUEST,
            message="查询失败",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    # 验证用户权限
    if app_data.author != user_sub:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=ResponseData(
            code=status.HTTP_403_FORBIDDEN,
            message="无权发布他人创建的应用",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    # 发布应用
    if not await AppCenterManager.publish_app(app_id):
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="发布失败",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=BaseAppOperationRsp(
        code=status.HTTP_200_OK,
        message="发布成功",
        result=BaseAppOperationMsg(appId=app_id),
    ).model_dump(exclude_none=True, by_alias=True))


@router.put("/{appId}", dependencies=[Depends(verify_csrf_token)], response_model=Union[ModFavAppRsp, ResponseData])
async def modify_favorite_application(  # noqa: ANN201
    app_id: Annotated[str, Path(..., alias="appId", description="应用ID")],
    request: Annotated[ModFavAppRequest, Body(...)],
    user_sub: Annotated[str, Depends(get_user)],
):
    """更改应用收藏状态"""
    flag = await AppCenterManager.modify_favorite_app(app_id, user_sub, favorited=request.favorited)
    if flag == AppCenterManager.ModFavAppFlag.NOT_FOUND:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=ResponseData(
            code=status.HTTP_404_NOT_FOUND,
            message="找不到应用",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    if flag == AppCenterManager.ModFavAppFlag.BAD_REQUEST:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="不可重复操作",
                result={},
            ).model_dump(exclude_none=True, by_alias=True))
    if flag == AppCenterManager.ModFavAppFlag.INTERNAL_ERROR:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="操作失败",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=ModFavAppRsp(
        code=status.HTTP_200_OK,
        message="操作成功",
        result=ModFavAppMsg(
            appId=app_id,
            favorited=request.favorited,
        ),
    ).model_dump(exclude_none=True, by_alias=True))
