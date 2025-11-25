# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""语义接口中心相关数据结构"""

import uuid
from typing import Any

from pydantic import BaseModel, Field

from .flow_topology import NodeServiceItem
from .response_data import ResponseData


class UpdateServiceRequest(BaseModel):
    """POST /api/service 请求数据结构"""

    service_id: uuid.UUID | None = Field(None, alias="serviceId", description="服务ID（更新时传递）")
    data: dict[str, Any] = Field(..., description="对应 YAML 内容的数据对象")


class ChangeFavouriteServiceRequest(BaseModel):
    """PUT /api/service/{serviceId} 请求数据结构"""

    favorited: bool = Field(..., description="是否收藏")


class ServiceCardItem(BaseModel):
    """语义接口中心：服务卡片数据结构"""

    service_id: uuid.UUID = Field(..., alias="serviceId", description="服务ID")
    name: str = Field(..., description="服务名称")
    description: str = Field(..., description="服务简介")
    author: str = Field(..., description="服务作者")
    favorited: bool = Field(..., description="是否已收藏")


class ServiceApiData(BaseModel):
    """语义接口中心：服务 API 接口属性数据结构"""

    name: str = Field(..., description="接口名称")
    path: str = Field(..., description="接口路径")
    description: str = Field(..., description="接口描述")


class BaseServiceOperationMsg(BaseModel):
    """语义接口中心：基础服务操作Result数据结构"""

    service_id: uuid.UUID = Field(..., alias="serviceId", description="服务ID")


class GetServiceListMsg(BaseModel):
    """GET /api/service Result数据结构"""

    current_page: int = Field(..., alias="currentPage", description="当前页码")
    total_count: int = Field(..., alias="totalCount", description="总服务数")
    services: list[ServiceCardItem] = Field(..., description="解析后的服务列表")


class GetServiceListRsp(ResponseData):
    """GET /api/service 返回数据结构"""

    result: GetServiceListMsg = Field(..., title="Result")


class UpdateServiceMsg(BaseModel):
    """语义接口中心：服务属性数据结构"""

    service_id: uuid.UUID = Field(..., alias="serviceId", description="服务ID")
    name: str = Field(..., description="服务名称")
    apis: list[ServiceApiData] = Field(..., description="解析后的接口列表")


class UpdateServiceRsp(ResponseData):
    """POST /api/service 返回数据结构"""

    result: UpdateServiceMsg = Field(..., title="Result")


class GetServiceDetailMsg(BaseModel):
    """GET /api/service/{serviceId} Result数据结构"""

    service_id: uuid.UUID = Field(..., alias="serviceId", description="服务ID")
    name: str = Field(..., description="服务名称")
    apis: list[ServiceApiData] | None = Field(default=None, description="解析后的接口列表")
    data: dict[str, Any] | None = Field(default=None, description="YAML 内容数据对象")


class GetServiceDetailRsp(ResponseData):
    """GET /api/service/{serviceId} 返回数据结构"""

    result: GetServiceDetailMsg = Field(..., title="Result")


class DeleteServiceRsp(ResponseData):
    """DELETE /api/service/{serviceId} 返回数据结构"""

    result: BaseServiceOperationMsg = Field(..., title="Result")


class ChangeFavouriteServiceMsg(BaseModel):
    """PUT /api/service/{serviceId} Result数据结构"""

    service_id: uuid.UUID = Field(..., alias="serviceId", description="服务ID")
    favorited: bool = Field(..., description="是否已收藏")


class ChangeFavouriteServiceRsp(ResponseData):
    """PUT /api/service/{serviceId} 返回数据结构"""

    result: ChangeFavouriteServiceMsg = Field(..., title="Result")


class NodeServiceListMsg(BaseModel):
    """GET /api/flow/service result"""

    services: list[NodeServiceItem] = Field(description="服务列表", default=[])


class NodeServiceListRsp(ResponseData):
    """GET /api/flow/service 返回数据结构"""

    result: NodeServiceListMsg
