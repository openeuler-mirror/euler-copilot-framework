"""Flow和Service等外置配置数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field

from apps.entities.enum_var import (
    AppPermissionsType,
    CallType,
    MetadataType,
)


class Step(BaseModel):
    """Flow中Step的数据"""

    name: str
    confirm: bool = False
    call_type: str
    params: dict[str, Any] = {}
    next: Optional[str] = None


class NextFlow(BaseModel):
    """Flow中“下一步”的数据格式"""

    id: str
    plugin: Optional[str] = None
    question: Optional[str] = None


class Flow(BaseModel):
    """Flow（工作流）的数据格式"""

    on_error: Optional[Step] = Step(
        name="error",
        call_type="llm",
        params={
            "user_prompt": "当前工具执行发生错误，原始错误信息为：{data}. 请向用户展示错误信息，并给出可能的解决方案。\n\n背景信息：{context}",
        },
    )
    steps: dict[str, Step]
    next_flow: Optional[list[NextFlow]] = None


class StepPool(BaseModel):
    """Step信息

    collection: step_pool
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    name: str
    description: str


class FlowPool(BaseModel):
    """Flow信息

    collection: flow_pool
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    name: str
    description: str
    data: Flow


class CallMetadata(BaseModel):
    """Call工具信息

    key: call
    """

    id: str = Field(alias="_id", description="Call的ID", default_factory=lambda: str(uuid.uuid4()))
    type: CallType = Field(description="Call的类型")
    name: str = Field(description="Call的名称")
    description: str = Field(description="Call的描述")
    path: str = Field(description="""
                        Call的路径。
                        当为系统Call时，路径就是ID，例如：“LLM”；
                        当为Python Call时，要加上Service名称，例如 “tune::call.tune.CheckSystem”
                    """)


class MetadataBase(BaseModel):
    """Service或App的元数据"""

    type: MetadataType = Field(description="元数据类型")
    id: str = Field(alias="_id", description="元数据ID")
    name: str = Field(description="元数据名称")
    description: str = Field(description="元数据描述")
    version: str = Field(description="元数据版本")
    author: str = Field(description="创建者的用户名")


class ServiceApiAuthOidc(BaseModel):
    """Service的API鉴权方式的OIDC配置"""

    client_id: str = Field(description="OIDC客户端ID")
    client_secret: str = Field(description="OIDC客户端密钥")


class ServiceApiAuthKeyVal(BaseModel):
    """Service的API鉴权方式的键值对"""

    name: str = Field(description="鉴权参数名称")
    value: str = Field(description="鉴权参数值")


class ServiceApiAuth(BaseModel):
    """Service的API鉴权方式"""

    header: list[ServiceApiAuthKeyVal] = Field(description="HTTP头鉴权配置", default=[])
    cookie: list[ServiceApiAuthKeyVal] = Field(description="HTTP Cookie鉴权配置", default=[])
    query: list[ServiceApiAuthKeyVal] = Field(description="HTTP URL参数鉴权配置", default=[])
    oidc: Optional[ServiceApiAuthOidc] = Field(description="OIDC鉴权配置", default=None)


class ServiceApiConfig(BaseModel):
    """Service的API配置"""

    server: str = Field(description="服务器地址", pattern=r"^(https|http)://.*$")
    auth: Optional[ServiceApiAuth] = Field(description="API鉴权方式", default=None)


class ServiceMetadata(MetadataBase):
    """Service的元数据"""

    type: MetadataType = MetadataType.SERVICE
    api: ServiceApiConfig = Field(description="API配置")


class AppLinks(BaseModel):
    """App的相关链接"""

    title: str = Field(description="链接标题")
    url: str = Field(description="链接URL")


class AppPermissions(BaseModel):
    """App的权限配置"""

    type: AppPermissionsType = Field(description="权限类型", default=AppPermissionsType.PRIVATE)
    users: list[str] = Field(description="可访问的用户列表", default=[])


class AppMetadata(MetadataBase):
    """App的元数据"""

    type: MetadataType = MetadataType.APP
    links: list[AppLinks] = Field(description="相关链接", default=[])
    first_questions: list[str] = Field(description="首次提问", default=[])
    history_len: int = Field(description="对话轮次", default=3, le=10)
    permissions: Optional[AppPermissions] = Field(description="应用权限配置", default=None)


class ServiceAPISpec(BaseModel):
    """外部服务API信息"""

    name: str = Field(description="OpenAPI文件名")
    description: str = Field(description="OpenAPI中关于API的Summary")
    size: int = Field(description="OpenAPI文件大小（单位：KB）")
    path: str = Field(description="OpenAPI文件路径")
    hash: str = Field(description="OpenAPI文件的hash值")


class Service(BaseModel):
    """外部服务信息

    collection: service
    """

    metadata: ServiceMetadata
    name: str
    description: str
    dir_path: str


class App(BaseModel):
    """应用信息

    collection: app
    """

    metadata: AppMetadata
    name: str
    description: str
    dir_path: str
