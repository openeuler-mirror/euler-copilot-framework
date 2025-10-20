# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""应用中心相关 API 基础数据结构定义"""

from pydantic import BaseModel, Field

from apps.schemas.enum_var import AppType, PermissionType


class AppCenterCardItem(BaseModel):
    """应用中心卡片数据结构"""

    app_id: str = Field(..., alias="appId", description="应用ID")
    app_type: AppType = Field(..., alias="appType", description="应用类型")
    icon: str = Field(..., description="应用图标")
    name: str = Field(..., description="应用名称")
    description: str = Field(..., description="应用简介")
    author: str = Field(..., description="应用作者")
    author_name: str = Field(..., alias="authorName", description="应用作者用户名")
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

    id: str = Field(..., description="工作流ID")
    name: str = Field(default="", description="工作流名称")
    description: str = Field(default="", description="工作流简介")
    debug: bool = Field(default=False, description="是否经过调试")


class AppData(BaseModel):
    """应用信息数据结构"""

    app_type: AppType = Field(..., alias="appType", description="应用类型")
    icon: str = Field(default="", description="图标")
    name: str = Field(..., max_length=20, description="应用名称")
    description: str = Field(..., max_length=150, description="应用简介")
    links: list[AppLink] = Field(default=[], description="相关链接", max_length=5)
    first_questions: list[str] = Field(
        default=[], alias="recommendedQuestions", description="推荐问题", max_length=3)
    history_len: int = Field(3, alias="dialogRounds", ge=1, le=10, description="对话轮次（1～10）")
    llm: str = Field(default="empty", description="大模型ID")
    permission: AppPermissionData = Field(
        default_factory=lambda: AppPermissionData(authorizedUsers=None), description="权限配置")
    workflows: list[AppFlowInfo] = Field(default=[], description="工作流信息列表")
    mcp_service: list[str] = Field(default=[], alias="mcpService", description="MCP服务id列表")
