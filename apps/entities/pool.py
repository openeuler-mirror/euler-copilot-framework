"""App和Service等数据库内数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from apps.entities.enum_var import CallType
from apps.entities.flow import AppLink, Permission
from apps.entities.flow_topology import PositionItem


class BaseData(BaseModel):
    """Pool的基础信息"""

    id: str = Field(alias="_id")
    name: str
    description: str
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=timezone.utc).timestamp(), 3))


class ServiceApiInfo(BaseModel):
    """外部服务API信息"""

    filename: str = Field(description="OpenAPI文件名")
    description: str = Field(description="OpenAPI中关于API的Summary")
    path: str = Field(description="OpenAPI文件路径")


class ServicePool(BaseData):
    """外部服务信息

    collection: service
    """

    author: str = Field(description="作者的用户ID")
    permission: Permission = Field(description="服务可见性配置", default=Permission())
    favorites: list[str] = Field(description="收藏此服务的用户列表", default=[])
    openapi_hash: str = Field(description="服务关联的 OpenAPI YAML 文件哈希")
    openapi_spec: dict = Field(description="服务关联的 OpenAPI 文件内容")


class CallPool(BaseData):
    """Call信息

    collection: call

    “path”的格式如下：
    1. Python代码会被导入成包，路径格式为`python::<package_name>::<call_name>`，用于查找Call的包路径和类路径
    """

    type: CallType = Field(description="Call的类型")
    path: str = Field(description="Call的路径")


class Node(BaseData):
    """Node合并后的信息（不存库）"""

    service_id: Optional[str] = Field(description="Node所属的Service ID", default=None)
    call_id: str = Field(description="所使用的Call的ID")
    params_schema: dict[str, Any] = Field(description="Node的参数schema", default={})
    output_schema: dict[str, Any] = Field(description="Node输出的完整Schema", default={})


class NodePool(BaseData):
    """Node合并前的信息（作为附带信息的指针）

    collection: node

    annotation为Node的路径，指示Node的类型、来源等
    annotation的格式如下：
    1. 无路径（如对应的Call等）：为None
    2. 从openapi中获取：`openapi::<file_name>`
    """

    service_id: Optional[str] = Field(description="Node所属的Service ID", default=None)
    call_id: str = Field(description="所使用的Call的ID")
    annotation: Optional[str] = Field(description="Node的注释", default=None)
    known_params: Optional[dict[str, Any]] = Field(description="已知的用于Call部分的参数，独立于输入和输出之外", default=None)
    override_input: Optional[dict[str, Any]] = Field(description="Node的输入Schema；用于描述Call的参数中特定的字段", default=None)
    override_output: Optional[dict[str, Any]] = Field(description="Node的输出Schema；用于描述Call的输出中特定的字段", default=None)


class AppFlow(BaseData):
    """Flow的元数据；会被存储在App下面"""

    enabled: bool = Field(description="是否启用", default=True)
    path: str = Field(description="Flow的路径")
    focus_point: PositionItem = Field(
        description="Flow的视觉焦点", default=PositionItem(x=0, y=0))


class AppPool(BaseData):
    """应用信息

    collection: app
    """

    author: str = Field(description="作者的用户ID")
    type: str = Field(description="应用类型", default="default")
    icon: str = Field(description="应用图标")
    published: bool = Field(description="是否发布", default=False)
    links: list[AppLink] = Field(description="相关链接", default=[])
    first_questions: list[str] = Field(description="推荐问题", default=[])
    history_len: int = Field(3, ge=1, le=10, description="对话轮次（1～10）")
    permission: Permission = Field(description="应用权限配置", default=Permission())
    flows: list[AppFlow] = Field(description="Flow列表", default=[])
    favorites: list[str] = Field(description="收藏此应用的用户列表", default=[])
    hashes: dict[str, str] = Field(description="关联文件的hash值", default={})
