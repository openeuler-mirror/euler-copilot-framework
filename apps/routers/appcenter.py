"""FastAPI 应用中心相关路由

Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""

import logging
from typing import Annotated, Optional, Union

from fastapi import APIRouter, Body, Depends, Path, Query, status
from fastapi.responses import JSONResponse

from apps.dependency.csrf import verify_csrf_token
from apps.dependency.user import get_user, verify_user
from apps.entities.appcenter import AppFlowInfo, AppPermissionData
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

logger = logging.getLogger("ray")
router = APIRouter(
    prefix="/api/app",
    tags=["appcenter"],
    dependencies=[Depends(verify_user)],
)


@router.get("", response_model=Union[GetAppListRsp, ResponseData])
async def get_applications(  # noqa: PLR0913
    user_sub: Annotated[str, Depends(get_user)],
    *,
    my_app: Annotated[bool, Query(..., alias="createdByMe", description="筛选我创建的")] = False,
    my_fav: Annotated[bool, Query(..., alias="favorited", description="筛选我收藏的")] = False,
    search_type: Annotated[SearchType, Query(..., alias="searchType", description="搜索类型")] = SearchType.ALL,
    keyword: Annotated[Optional[str], Query(..., alias="keyword", description="搜索关键字")] = None,
    page: Annotated[int, Query(..., alias="page", ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(..., alias="pageSize", ge=1, le=100, description="每页条数")] = 16,
) -> JSONResponse:
    """获取应用列表"""
    if my_app and my_fav:  # 只能同时使用一个过滤条件
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="INVALID_PARAMETER",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )

    app_cards, total_apps = [], -1
    if my_app:  # 筛选我创建的
        app_cards, total_apps = await AppCenterManager.fetch_user_apps(user_sub, search_type, keyword, page, page_size)
    elif my_fav:  # 筛选已收藏的
        app_cards, total_apps = await AppCenterManager.fetch_favorite_apps(
            user_sub,
            search_type,
            keyword,
            page,
            page_size,
        )
    else:  # 获取所有应用
        app_cards, total_apps = await AppCenterManager.fetch_all_apps(user_sub, search_type, keyword, page, page_size)
    if total_apps == -1:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=GetAppListRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=GetAppListMsg(
                currentPage=page,
                totalApps=total_apps,
                applications=app_cards,
            ),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.post("", dependencies=[Depends(verify_csrf_token)], response_model=Union[BaseAppOperationRsp, ResponseData])
async def create_or_update_application(
    request: Annotated[CreateAppRequest, Body(...)],
    user_sub: Annotated[str, Depends(get_user)],
) -> JSONResponse:
    """创建或更新应用"""
    app_id = request.app_id
    if app_id:  # 更新应用
        try:
            await AppCenterManager.update_app(user_sub, app_id, request)
        except ValueError:
            logger.exception("[AppCenter] 更新应用请求无效")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="BAD_REQUEST",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        except PermissionError:
            logger.exception("[AppCenter] 更新应用鉴权失败")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content=ResponseData(
                    code=status.HTTP_403_FORBIDDEN,
                    message="UNAUTHORIZED",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        except Exception:
            logger.exception("[AppCenter] 更新应用失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
    else:  # 创建应用
        try:
            app_id = await AppCenterManager.create_app(user_sub, request)
        except Exception:
            logger.exception("[AppCenter] 创建应用失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=BaseAppOperationRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=BaseAppOperationMsg(appId=app_id),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.get("/recent", response_model=Union[GetRecentAppListRsp, ResponseData])
async def get_recently_used_applications(
    user_sub: Annotated[str, Depends(get_user)],
    count: Annotated[int, Query(..., ge=1, le=10)] = 5,
) -> JSONResponse:
    """获取最近使用的应用"""
    try:
        recent_apps = await AppCenterManager.get_recently_used_apps(count, user_sub)
    except Exception:
        logger.exception("[AppCenter] 获取最近使用的应用失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=GetRecentAppListRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=recent_apps,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.get("/{appId}", response_model=Union[GetAppPropertyRsp, ResponseData])
async def get_application(
    app_id: Annotated[str, Path(..., alias="appId", description="应用ID")],
) -> JSONResponse:
    """获取应用详情"""
    try:
        app_data = await AppCenterManager.fetch_app_data_by_id(app_id)
    except ValueError:
        logger.exception("[AppCenter] 获取应用详情请求无效")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="INVALID_APP_ID",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    except Exception:
        logger.exception("[AppCenter] 获取应用详情失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    workflows = [
        AppFlowInfo(
            id=flow.id,
            name=flow.name,
            description=flow.description,
            debug=flow.debug,
        )
        for flow in app_data.flows
    ]
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=GetAppPropertyRsp(
            code=status.HTTP_200_OK,
            message="OK",
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
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.delete(
    "/{appId}",
    dependencies=[Depends(verify_csrf_token)],
    response_model=Union[BaseAppOperationRsp, ResponseData],
)
async def delete_application(
    app_id: Annotated[str, Path(..., alias="appId", description="应用ID")],
    user_sub: Annotated[str, Depends(get_user)],
) -> JSONResponse:
    """删除应用"""
    try:
        await AppCenterManager.delete_app(app_id, user_sub)
    except ValueError:
        logger.exception("[AppCenter] 删除应用请求无效")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="INVALID_APP_ID",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    except PermissionError:
        logger.exception("[AppCenter] 删除应用鉴权失败")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=ResponseData(
                code=status.HTTP_403_FORBIDDEN,
                message="UNAUTHORIZED",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    except Exception:
        logger.exception("[AppCenter] 删除应用失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=BaseAppOperationRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=BaseAppOperationMsg(appId=app_id),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.post("/{appId}", dependencies=[Depends(verify_csrf_token)], response_model=BaseAppOperationRsp)
async def publish_application(
    app_id: Annotated[str, Path(..., alias="appId", description="应用ID")],
    user_sub: Annotated[str, Depends(get_user)],
) -> JSONResponse:
    """发布应用"""
    try:
        await AppCenterManager.publish_app(app_id, user_sub)
    except ValueError:
        logger.exception("[AppCenter] 发布应用请求无效")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="BAD_REQUEST",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    except PermissionError:
        logger.exception("[AppCenter] 发布应用鉴权失败")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=ResponseData(
                code=status.HTTP_403_FORBIDDEN,
                message="UNAUTHORIZED",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    except Exception:
        logger.exception("[AppCenter] 发布应用失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=BaseAppOperationRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=BaseAppOperationMsg(appId=app_id),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.put("/{appId}", dependencies=[Depends(verify_csrf_token)], response_model=Union[ModFavAppRsp, ResponseData])
async def modify_favorite_application(
    app_id: Annotated[str, Path(..., alias="appId", description="应用ID")],
    request: Annotated[ModFavAppRequest, Body(...)],
    user_sub: Annotated[str, Depends(get_user)],
) -> JSONResponse:
    """更改应用收藏状态"""
    try:
        await AppCenterManager.modify_favorite_app(app_id, user_sub, favorited=request.favorited)
    except ValueError:
        logger.exception("[AppCenter] 修改收藏状态请求无效")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="BAD_REQUEST",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    except Exception:
        logger.exception("[AppCenter] 修改收藏状态失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ModFavAppRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=ModFavAppMsg(
                appId=app_id,
                favorited=request.favorited,
            ),
        ).model_dump(exclude_none=True, by_alias=True),
    )
