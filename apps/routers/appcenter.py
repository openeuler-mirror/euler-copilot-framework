# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 应用中心相关路由"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from apps.dependency.user import verify_personal_token, verify_session
from apps.exceptions import InstancePermissionError
from apps.models import AppType, PermissionType
from apps.schemas.appcenter import (
    AppFlowInfo,
    AppMcpServiceInfo,
    AppPermissionData,
    BaseAppOperationMsg,
    BaseAppOperationRsp,
    ChangeFavouriteAppMsg,
    ChangeFavouriteAppRequest,
    ChangeFavouriteAppRsp,
    CreateAppRequest,
    GetAppListMsg,
    GetAppListRsp,
    GetAppPropertyMsg,
    GetAppPropertyRsp,
    GetRecentAppListRsp,
)
from apps.schemas.enum_var import AppFilterType
from apps.schemas.flow import AgentAppMetadata, FlowAppMetadata
from apps.schemas.response_data import ResponseData
from apps.services.appcenter import AppCenterManager
from apps.services.mcp_service import MCPServiceManager

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/app",
    tags=["appcenter"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)


@router.get("", response_model=GetAppListRsp | ResponseData)
async def get_applications(  # noqa: PLR0913
    request: Request,
    *,
    createdByMe: bool = False, favorited: bool = False,  # noqa: N803
    keyword: str | None = None, appType: AppType | None = None,  # noqa: N803
    page: Annotated[int, Query(ge=1)] = 1,
) -> JSONResponse:
    """获取应用列表"""
    user_id: str = request.state.user_id
    if createdByMe and favorited:  # 只能同时使用一个过滤条件
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="INVALID_PARAMETER",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )

    try:
        filter_type = (
            AppFilterType.USER if createdByMe else (AppFilterType.FAVORITE if favorited else AppFilterType.ALL)
        )
        app_cards, total_apps = await AppCenterManager.fetch_apps(
            user_id,
            keyword,
            appType,
            page,
            filter_type,
        )
    except Exception:
        logger.exception("[AppCenter] 获取应用列表失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            GetAppListRsp(
                code=status.HTTP_200_OK,
                message="OK",
                result=GetAppListMsg(
                    currentPage=page,
                    totalApps=total_apps,
                    applications=app_cards,
                ),
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@router.post("", response_model=BaseAppOperationRsp | ResponseData)
async def create_or_update_application(raw_request: Request, request: CreateAppRequest) -> JSONResponse:
    """创建或更新应用"""
    user_id: str = raw_request.state.user_id

    app_id = request.app_id
    if app_id:  # 更新应用
        try:
            await AppCenterManager.update_app(user_id, app_id, request)
        except ValueError:
            logger.exception("[AppCenter] 更新应用请求无效")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=jsonable_encoder(
                    ResponseData(
                        code=status.HTTP_400_BAD_REQUEST,
                        message="BAD_REQUEST",
                        result={},
                    ).model_dump(exclude_none=True, by_alias=True),
                ),
            )
        except InstancePermissionError:
            logger.exception("[AppCenter] 更新应用鉴权失败")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content=jsonable_encoder(
                    ResponseData(
                        code=status.HTTP_403_FORBIDDEN,
                        message="UNAUTHORIZED",
                        result={},
                    ).model_dump(exclude_none=True, by_alias=True),
                ),
            )
        except Exception:
            logger.exception("[AppCenter] 更新应用失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=jsonable_encoder(
                    ResponseData(
                        code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        message="ERROR",
                        result={},
                    ).model_dump(exclude_none=True, by_alias=True),
                ),
            )
    else:  # 创建应用
        try:
            app_id = await AppCenterManager.create_app(user_id, request)
        except Exception:
            logger.exception("[AppCenter] 创建应用失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=jsonable_encoder(
                    ResponseData(
                        code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        message="ERROR",
                        result={},
                    ).model_dump(exclude_none=True, by_alias=True),
                ),
            )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            BaseAppOperationRsp(
                code=status.HTTP_200_OK,
                message="OK",
                result=BaseAppOperationMsg(appId=app_id),
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@router.get("/recent", response_model=GetRecentAppListRsp | ResponseData)
async def get_recently_used_applications(
    request: Request,
    count: Annotated[int, Query(ge=1, le=10)] = 5,
) -> JSONResponse:
    """获取最近使用的应用"""
    user_id: str = request.state.user_id
    try:
        recent_apps = await AppCenterManager.get_recently_used_apps(count, user_id)
    except Exception:
        logger.exception("[AppCenter] 获取最近使用的应用失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            GetRecentAppListRsp(
                code=status.HTTP_200_OK,
                message="OK",
                result=recent_apps,
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@router.get("/{appId}", response_model=GetAppPropertyRsp | ResponseData)
async def get_application(appId: Annotated[uuid.UUID, Path()]) -> JSONResponse:  # noqa: N803
    """获取应用详情"""
    try:
        app_data = await AppCenterManager.fetch_app_metadata_by_id(appId)
    except ValueError:
        logger.exception("[AppCenter] 获取应用详情请求无效")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="INVALID_APP_ID",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    except Exception:
        logger.exception("[AppCenter] 获取应用详情失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )

    # 根据 Metadata 类型组装对应的 GetAppPropertyMsg
    if isinstance(app_data, FlowAppMetadata):
        # 处理工作流应用（FLOW类型）
        workflows = [
            AppFlowInfo(
                id=flow.id,
                name=flow.name,
                description=flow.description,
                debug=flow.debug,
            )
            for flow in app_data.flows
        ]
        result_msg = GetAppPropertyMsg(
            appId=str(app_data.id),
            appType=app_data.app_type,
            published=app_data.published,
            name=app_data.name,
            description=app_data.description,
            icon=app_data.icon,
            links=app_data.links,
            recommendedQuestions=app_data.first_questions,
            dialogRounds=app_data.history_len,
            permission=AppPermissionData(
                visibility=app_data.permission.type if app_data.permission else PermissionType.PRIVATE,
                authorizedUsers=app_data.permission.users if app_data.permission else [],
            ),
            workflows=workflows,
            mcpService=[],
        )
    elif isinstance(app_data, AgentAppMetadata):
        # 处理智能体应用（AGENT类型）
        mcp_service = []
        if app_data.mcp_service:
            for service in app_data.mcp_service:
                mcp_collection = await MCPServiceManager.get_mcp_service(service)
                # 当 mcp_collection 为 None 时忽略当前的 MCP Server
                if mcp_collection is not None:
                    mcp_service.append(AppMcpServiceInfo(
                        id=uuid.UUID(service) if isinstance(service, str) else service,
                        name=mcp_collection.name,
                        description=mcp_collection.description,
                    ))
        result_msg = GetAppPropertyMsg(
            appId=str(app_data.id),
            appType=app_data.app_type,
            published=app_data.published,
            name=app_data.name,
            description=app_data.description,
            icon=app_data.icon,
            links=[],
            recommendedQuestions=[],
            dialogRounds=app_data.history_len,
            permission=AppPermissionData(
                visibility=app_data.permission.type if app_data.permission else PermissionType.PRIVATE,
                authorizedUsers=app_data.permission.users if app_data.permission else [],
            ),
            workflows=[],
            mcpService=mcp_service,
        )
    else:
        logger.error("[AppCenter] 未知的应用元数据类型: %s", type(app_data).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="UNKNOWN_APP_TYPE",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            GetAppPropertyRsp(
                code=status.HTTP_200_OK,
                message="OK",
                result=result_msg,
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@router.delete(
    "/{appId}",
    response_model=BaseAppOperationRsp | ResponseData,
)
async def delete_application(
    request: Request,
    app_id: Annotated[uuid.UUID, Path(..., alias="appId", description="应用ID")],
) -> JSONResponse:
    """删除应用"""
    user_id: str = request.state.user_id
    try:
        await AppCenterManager.delete_app(app_id, user_id)
    except ValueError:
        logger.exception("[AppCenter] 删除应用请求无效")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="INVALID_APP_ID",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    except InstancePermissionError:
        logger.exception("[AppCenter] 删除应用鉴权失败")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_403_FORBIDDEN,
                    message="UNAUTHORIZED",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    except Exception:
        logger.exception("[AppCenter] 删除应用失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            BaseAppOperationRsp(
                code=status.HTTP_200_OK,
                message="OK",
                result=BaseAppOperationMsg(appId=app_id),
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@router.post("/{appId}", response_model=BaseAppOperationRsp)
async def publish_application(
    request: Request,
    app_id: Annotated[uuid.UUID, Path(..., alias="appId", description="应用ID")],
) -> JSONResponse:
    """发布应用"""
    user_id: str = request.state.user_id
    try:
        published = await AppCenterManager.update_app_publish_status(app_id, user_id)
        if not published:
            logger.error("[AppCenter] 发布应用失败")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=jsonable_encoder(
                    ResponseData(
                        code=status.HTTP_400_BAD_REQUEST,
                        message="发布应用失败",
                        result={},
                    ).model_dump(exclude_none=True, by_alias=True),
                ),
            )
    except InstancePermissionError:
        logger.exception("[AppCenter] 发布应用鉴权失败")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_403_FORBIDDEN,
                    message="鉴权失败",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    except Exception as e:
        logger.exception("[AppCenter] 发布应用失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message=f"发布应用失败: {e!s}",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            BaseAppOperationRsp(
                code=status.HTTP_200_OK,
                message="OK",
                result=BaseAppOperationMsg(appId=app_id),
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@router.put("/{appId}", response_model=ChangeFavouriteAppRsp | ResponseData)
async def modify_favorite_application(
    raw_request: Request,
    app_id: Annotated[uuid.UUID, Path(..., alias="appId", description="应用ID")],
    request: Annotated[ChangeFavouriteAppRequest, Body(...)],
) -> JSONResponse:
    """更改应用收藏状态"""
    user_id: str = raw_request.state.user_id
    try:
        await AppCenterManager.modify_favorite_app(app_id, user_id, favorited=request.favorited)
    except ValueError:
        logger.exception("[AppCenter] 修改收藏状态请求无效")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="BAD_REQUEST",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    except Exception:
        logger.exception("[AppCenter] 修改收藏状态失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ChangeFavouriteAppRsp(
                code=status.HTTP_200_OK,
                message="OK",
                result=ChangeFavouriteAppMsg(
                    appId=app_id,
                    favorited=request.favorited,
                ),
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )
