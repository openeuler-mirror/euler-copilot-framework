"""应用中心相关 API 基础数据结构定义

Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""
from typing import Optional

from pydantic import BaseModel, Field

from apps.entities.enum_var import PermissionType
from apps.entities.flow import AppLink


class AppCenterCardItem(BaseModel):
    """应用中心卡片数据结构"""

    app_id: str = Field(..., alias="appId", description="应用ID")
    icon: str = Field(..., description="应用图标")
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
    users: Optional[list[str]] = Field(
        None,
        alias="authorizedUsers",
        description="附加人员名单（如果可见性为部分人可见）",
    )


class AppData(BaseModel):
    """应用信息数据结构"""

    icon: str = Field(default="", description="图标")
    name: str = Field(..., max_length=20, description="应用名称")
    description: str = Field(..., max_length=150, description="应用简介")
    links: list[AppLink] = Field(default=[], description="相关链接", max_length=5)
    first_questions: list[str] = Field(
        default=[], alias="recommendedQuestions", description="推荐问题", max_length=3)
    history_len: int = Field(3, alias="dialogRounds", ge=1, le=10, description="对话轮次（1～10）")
    permission: AppPermissionData = Field(
        default_factory=lambda: AppPermissionData(authorizedUsers=None), description="权限配置")
    workflows: list[str] = Field(default=[], description="工作流ID列表")
