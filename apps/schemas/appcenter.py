# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""应用中心相关 API 基础数据结构定义"""

import uuid

from pydantic import BaseModel, Field

from apps.models import AppType, PermissionType

from .response_data import ResponseData


class AppCenterCardItem(BaseModel):
    """应用中心卡片数据结构"""

    app_id: uuid.UUID = Field(..., alias="appId", description="应用ID")
    app_type: AppType = Field(..., alias="appType", description="应用类型")
    name: str = Field(..., description="应用名称")
    description: str = Field(..., description="应用简介")
    author: str = Field(..., description="应用作者")
    favorited: bool = Field(..., description="是否已收藏")
    published: bool = Field(default=True, description="是否已发布")


class AppPermissionData(BaseModel):
    """应用权限数据结构"""

    type: PermissionType = Field(
        default=PermissionType.PRIVATE,
        alias="visibility",
        description="可见性（public/private/protected）",
    )
    users: list[str] | None = Field(
        None,
        alias="authorizedUsers",
        description="附加人员名单（如果可见性为部分人可见）",
    )


class AppLink(BaseModel):
    """App的相关链接"""

    title: str = Field(description="链接标题")
    url: str = Field(..., description="链接地址", pattern=r"^(https|http)://.*$")


class AppFlowInfo(BaseModel):
    """应用工作流数据结构"""

    id: uuid.UUID = Field(..., description="工作流ID")
    name: str = Field(default="", description="工作流名称")
    description: str = Field(default="", description="工作流简介")
    debug: bool = Field(default=False, description="是否经过调试")


class AppData(BaseModel):
    """应用信息数据结构"""

    app_type: AppType = Field(..., alias="appType", description="应用类型")
    name: str = Field(..., max_length=20, description="应用名称")
    description: str = Field(..., max_length=150, description="应用简介")
    links: list[AppLink] = Field(default=[], description="相关链接", max_length=5)
    first_questions: list[str] = Field(
        default=[], alias="recommendedQuestions", description="推荐问题", max_length=3)
    history_len: int = Field(3, alias="dialogRounds", ge=1, le=10, description="对话轮次（1～10）")
    permission: AppPermissionData = Field(
        default_factory=lambda: AppPermissionData(authorizedUsers=None), description="权限配置")
    workflows: list[AppFlowInfo] = Field(default=[], description="工作流信息列表")
    mcp_service: list[str] = Field(default=[], alias="mcpService", description="MCP服务id列表")


class AppMcpServiceInfo(BaseModel):
    """MCP服务信息"""

    id: uuid.UUID = Field(description="MCP服务ID")
    name: str = Field(description="MCP服务名称")
    description: str = Field(description="MCP服务描述")


class CreateAppRequest(AppData):
    """POST /api/app 请求数据结构"""

    app_id: uuid.UUID | None = Field(None, alias="appId", description="应用ID")


class ChangeFavouriteAppRequest(BaseModel):
    """PUT /api/app/{appId} 请求数据结构"""

    favorited: bool = Field(..., description="是否收藏")


class GetAppPropertyMsg(AppData):
    """GET /api/app/{appId} Result数据结构"""

    app_id: str = Field(..., alias="appId", description="应用ID")
    published: bool = Field(..., description="是否已发布")
    mcp_service: list[AppMcpServiceInfo] = Field(default=[], alias="mcpService", description="MCP服务信息列表")


class GetAppPropertyRsp(ResponseData):
    """GET /api/app/{appId} 返回数据结构"""

    result: GetAppPropertyMsg


class ChangeFavouriteAppMsg(BaseModel):
    """PUT /api/app/{appId} Result数据结构"""

    app_id: uuid.UUID = Field(..., alias="appId", description="应用ID")
    favorited: bool = Field(..., description="是否已收藏")


class ChangeFavouriteAppRsp(ResponseData):
    """PUT /api/app/{appId} 返回数据结构"""

    result: ChangeFavouriteAppMsg


class GetAppListMsg(BaseModel):
    """GET /api/app Result数据结构"""

    page_number: int = Field(..., alias="currentPage", description="当前页码")
    app_count: int = Field(..., alias="totalApps", description="总应用数")
    applications: list[AppCenterCardItem] = Field(..., description="应用列表")


class GetAppListRsp(ResponseData):
    """GET /api/app 返回数据结构"""

    result: GetAppListMsg


class RecentAppListItem(BaseModel):
    """GET /api/app/recent 列表项数据结构"""

    app_id: uuid.UUID = Field(..., alias="appId", description="应用ID")
    name: str = Field(..., description="应用名称")


class RecentAppList(BaseModel):
    """GET /api/app/recent Result数据结构"""

    applications: list[RecentAppListItem] = Field(..., description="最近使用的应用列表")


class GetRecentAppListRsp(ResponseData):
    """GET /api/app/recent 返回数据结构"""

    result: RecentAppList


class BaseAppOperationMsg(BaseModel):
    """基础应用操作Result数据结构"""

    app_id: uuid.UUID = Field(..., alias="appId", description="应用ID")


class BaseAppOperationRsp(ResponseData):
    """基础应用操作返回数据结构"""

    result: BaseAppOperationMsg

