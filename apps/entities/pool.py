"""App和Service等数据库内数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from apps.entities.enum_var import CallType


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


class CallPool(PoolBase):
    """Call信息

    collection: call
    """

    id: str = Field(description="Call的ID")
    type: CallType = Field(description="Call的类型")
    path: str = Field(description="Call的路径")


class NodePool(PoolBase):
    """Node信息

    collection: node
    注：
        1. 基类Call的ID，即meta_call，可以为None，表示该Node是系统Node
        2. 路径的格式：
            1. 系统Node的路径格式样例：“LLM”
            2. Python Node的路径格式样例：“tune::call.tune.CheckSystem”
    """

    id: str = Field(description="Node的ID", default_factory=lambda: str(uuid.uuid4()))
    created_at: None = None
    service_id: str = Field(description="Node所属的Service ID")
    call_id: str = Field(description="所使用的Call的ID")
    fixed_params: dict[str, Any] = Field(description="Node的固定参数", default={})
    params_schema: dict[str, Any] = Field(description="Node的参数schema；只包含用户可以改变的参数", default={})
    output_schema: dict[str, Any] = Field(description="Node的输出schema；做输出的展示用", default={})


class AppFlow(PoolBase):
    """Flow的元数据；会被存储在App下面"""

    enabled: bool = Field(description="是否启用", default=True)
    path: str = Field(description="Flow的路径")


class AppPool(PoolBase):
    """应用信息

    collection: app
    """

    author: str
    flows: list[AppFlow] = Field(description="Flow列表", default=[])
    hashes: dict[str, str] = Field(description="关联文件的hash值", default={})
