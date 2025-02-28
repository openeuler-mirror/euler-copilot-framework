"""FastAPI 语义接口中心相关路由

Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""

import logging
from typing import Annotated, Optional, Union

from fastapi import APIRouter, Body, Depends, Path, Query, status
from fastapi.responses import JSONResponse

from apps.dependency.csrf import verify_csrf_token
from apps.dependency.user import get_user, verify_user
from apps.entities.enum_var import SearchType
from apps.entities.request_data import ModFavServiceRequest, UpdateServiceRequest
from apps.entities.response_data import (
    BaseServiceOperationMsg,
    DeleteServiceRsp,
    GetServiceDetailMsg,
    GetServiceDetailRsp,
    GetServiceListMsg,
    GetServiceListRsp,
    ModFavServiceMsg,
    ModFavServiceRsp,
    ResponseData,
    UpdateServiceMsg,
    UpdateServiceRsp,
)
from apps.manager.service import ServiceCenterManager

logger = logging.getLogger("ray")
router = APIRouter(
    prefix="/api/service",
    tags=["service-center"],
    dependencies=[Depends(verify_user)],
)


@router.get("", response_model=Union[GetServiceListRsp, ResponseData])
async def get_service_list(  # noqa: PLR0913
    user_sub: Annotated[str, Depends(get_user)],
    *,
    my_service: Annotated[bool, Query(..., alias="createdByMe", description="筛选我创建的")] = False,
    my_fav: Annotated[bool, Query(..., alias="favorited", description="筛选我收藏的")] = False,
    search_type: Annotated[SearchType, Query(..., alias="searchType", description="搜索类型")] = SearchType.ALL,
    keyword: Annotated[Optional[str], Query(..., alias="keyword", description="搜索关键字")] = None,
    page: Annotated[int, Query(..., alias="page", ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(..., alias="pageSize", ge=1, le=100, description="每页数量")] = 16,
) -> JSONResponse:
    """获取服务列表"""
    if my_service and my_fav:  # 只能同时选择一个筛选条件
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="INVALID_PARAMETER",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )

    service_cards, total_count = [], -1
    try:
        if my_service:  # 筛选我创建的
            service_cards, total_count = await ServiceCenterManager.fetch_user_services(
                user_sub,
                search_type,
                keyword,
                page,
                page_size,
            )
        elif my_fav:  # 筛选我收藏的
            service_cards, total_count = await ServiceCenterManager.fetch_favorite_services(
                user_sub,
                search_type,
                keyword,
                page,
                page_size,
            )
        else:  # 获取所有服务
            service_cards, total_count = await ServiceCenterManager.fetch_all_services(
                user_sub,
                search_type,
                keyword,
                page,
                page_size,
            )
    except Exception:
        logger.exception("[ServiceCenter] 获取服务列表失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    if total_count == -1:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="INVALID_PARAMETER",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=GetServiceListRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=GetServiceListMsg(
                currentPage=page,
                totalCount=total_count,
                services=service_cards,
            ),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.post("", response_model=UpdateServiceRsp, dependencies=[Depends(verify_csrf_token)])
async def update_service(  # noqa: PLR0911
    user_sub: Annotated[str, Depends(get_user)],
    data: Annotated[UpdateServiceRequest, Body(..., description="上传 YAML 文本对应数据对象")],
) -> JSONResponse:
    """上传并解析服务"""
    if not data.service_id:
        try:
            service_id = await ServiceCenterManager.create_service(user_sub, data.data)
        except ValueError as e:  # OpenAPI YAML 接口字段不完整
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message=str(e),
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        except Exception:
            logger.exception("[ServiceCenter] 创建服务失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
    else:
        try:
            service_id = await ServiceCenterManager.update_service(user_sub, data.service_id, data.data)
        except ValueError as e:
            if str(e).startswith("Endpoint error"):  # OpenAPI YAML 接口字段不完整
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content=ResponseData(
                        code=status.HTTP_400_BAD_REQUEST,
                        message=str(e),
                        result={},
                    ).model_dump(exclude_none=True, by_alias=True),
                )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="INVALID_SERVICE_ID",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        except PermissionError:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content=ResponseData(
                    code=status.HTTP_403_FORBIDDEN,
                    message="UNAUTHORIZED",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        except Exception:
            logger.exception("[ServiceCenter] 更新服务失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
    try:
        name, apis = await ServiceCenterManager.get_service_apis(service_id)
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="INVALID_SERVICE_ID",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    except Exception:
        logger.exception("[ServiceCenter] 获取服务API失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    msg = UpdateServiceMsg(serviceId=service_id, name=name, apis=apis)
    rsp = UpdateServiceRsp(code=status.HTTP_200_OK, message="OK", result=msg)
    return JSONResponse(status_code=status.HTTP_200_OK, content=rsp.model_dump(exclude_none=True, by_alias=True))


@router.get("/{serviceId}", response_model=GetServiceDetailRsp)
async def get_service_detail(
    user_sub: Annotated[str, Depends(get_user)],
    service_id: Annotated[str, Path(..., alias="serviceId", description="服务ID")],
    *,
    edit: Annotated[bool, Query(..., description="是否为编辑模式")] = False,
) -> JSONResponse:
    """获取服务详情"""
    # 示例：返回指定服务的详情
    if edit:
        try:
            name, data = await ServiceCenterManager.get_service_data(user_sub, service_id)
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="INVALID_SERVICE_ID",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        except PermissionError:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content=ResponseData(
                    code=status.HTTP_403_FORBIDDEN,
                    message="UNAUTHORIZED",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        except Exception:
            logger.exception("[ServiceCenter] 获取服务数据失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        detail = GetServiceDetailMsg(serviceId=service_id, name=name, data=data)
    else:
        try:
            name, apis = await ServiceCenterManager.get_service_apis(service_id)
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="INVALID_SERVICE_ID",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        except Exception:
            logger.exception("[ServiceCenter] 获取服务API失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        detail = GetServiceDetailMsg(serviceId=service_id, name=name, apis=apis)
    rsp = GetServiceDetailRsp(code=status.HTTP_200_OK, message="OK", result=detail)
    return JSONResponse(status_code=status.HTTP_200_OK, content=rsp.model_dump(exclude_none=True, by_alias=True))


@router.delete("/{serviceId}", response_model=DeleteServiceRsp, dependencies=[Depends(verify_csrf_token)])
async def delete_service(
    user_sub: Annotated[str, Depends(get_user)],
    service_id: Annotated[str, Path(..., alias="serviceId", description="服务ID")],
) -> JSONResponse:
    """删除服务"""
    try:
        await ServiceCenterManager.delete_service(user_sub, service_id)
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="INVALID_SERVICE_ID",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    except PermissionError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=ResponseData(
                code=status.HTTP_403_FORBIDDEN,
                message="UNAUTHORIZED",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    except Exception:
        logger.exception("[ServiceCenter] 删除服务失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    msg = BaseServiceOperationMsg(serviceId=service_id)
    rsp = DeleteServiceRsp(code=status.HTTP_200_OK, message="OK", result=msg)
    return JSONResponse(status_code=status.HTTP_200_OK, content=rsp.model_dump(exclude_none=True, by_alias=True))


@router.put("/{serviceId}", response_model=ModFavServiceRsp, dependencies=[Depends(verify_csrf_token)])
async def modify_favorite_service(
    user_sub: Annotated[str, Depends(get_user)],
    service_id: Annotated[str, Path(..., alias="serviceId", description="服务ID")],
    data: Annotated[ModFavServiceRequest, Body(..., description="更改收藏状态请求对象")],
) -> JSONResponse:
    """修改服务收藏状态"""
    try:
        success = await ServiceCenterManager.modify_favorite_service(user_sub, service_id, favorited=data.favorited)
        if not success:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="INVALID_PARAMETER",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="INVALID_SERVICE_ID",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    except Exception:
        logger.exception("[ServiceCenter] 修改服务收藏状态失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    msg = ModFavServiceMsg(serviceId=service_id, favorited=data.favorited)
    rsp = ModFavServiceRsp(code=status.HTTP_200_OK, message="OK", result=msg)
    return JSONResponse(status_code=status.HTTP_200_OK, content=rsp.model_dump(exclude_none=True, by_alias=True))
