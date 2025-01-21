"""App和Service等数据库内数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from apps.entities.enum_var import CallType
from apps.entities.flow import AppLink, AppPermission


class PoolBase(BaseModel):
    """Pool的基础信息"""

    id: str
    name: str
    description: str
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=timezone.utc).timestamp(), 3))


class ServiceApiInfo(BaseModel):
    """外部服务API信息"""

    filename: str = Field(description="OpenAPI文件名")
    description: str = Field(description="OpenAPI中关于API的Summary")
    path: str = Field(description="OpenAPI文件路径")


class ServicePool(PoolBase):
    """外部服务信息

    collection: service
    """

    author: str
    api: list[ServiceApiInfo] = Field(description="API信息列表", default=[])
    hashes: dict[str, str] = Field(description="关联文件的hash值；Service作为整体更新或删除", default={})


class NodePool(PoolBase):
    """Node信息

    collection: node
    注：
        1. 基类Call的ID，即meta_call，可以为None，表示该Node是系统Node
        2. 路径的格式：
            1. 系统Node的路径格式样例：“LLM”
            2. Python Node的路径格式样例：“tune::call.tune.CheckSystem”
    """

    id: str = Field(description="Node的ID")
    type: CallType = Field(description="Call的类型")
    service: str = Field(description="服务名称")
    meta_call: Optional[str] = Field(description="基类Call的ID", default=None)
    input_schema: dict[str, Any] = Field(description="输入参数的schema", default={})
    output_schema: dict[str, Any] = Field(description="输出参数的schema", default={})
    params: dict[str, Any] = Field(description="参数", default={})
    path: str = Field(description="Node的路径；包括Node的作用域等")


class AppFlow(PoolBase):
    """Flow的元数据；会被存储在App下面"""

    enabled: bool = Field(description="是否启用", default=True)
    path: str = Field(description="Flow的路径")


class AppPool(PoolBase):
    """应用信息

    collection: app
    """

    author: str = Field(description="作者的用户ID")
    icon: str = Field(description="应用图标")
    published: bool = Field(description="是否发布", default=False)
    links: list[AppLink] = Field(description="相关链接", default=[])
    first_questions: list[str] = Field(description="推荐问题", default=[])
    history_len: int = Field(3, ge=1, le=10, description="对话轮次（1～10）")
    permission: AppPermission = Field(description="应用权限配置", default=AppPermission())
    flows: list[AppFlow] = Field(description="Flow列表", default=[])
    favorites: list[str] = Field(description="收藏此应用的用户列表", default=[])
    hashes: dict[str, str] = Field(description="关联文件的hash值", default={})
