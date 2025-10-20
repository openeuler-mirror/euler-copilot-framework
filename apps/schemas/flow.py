# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""App、Flow和Service等外置配置数据结构"""

from typing import Any

from pydantic import BaseModel, Field

from apps.schemas.appcenter import AppLink
from apps.schemas.enum_var import (
    AppType,
    EdgeType,
    MetadataType,
    PermissionType,
)
from apps.schemas.flow_topology import PositionItem


class Note(BaseModel):
    """Flow中Note的数据"""

    note_id: str = Field(description="备注的ID")
    text: str = Field(description="备注内容")
    position: PositionItem = Field(description="备注在画布上的位置", default=PositionItem(x=0, y=0))
    width: float = Field(description="备注的宽度", default=200.0)
    height: float = Field(description="备注的高度", default=100.0)


class Edge(BaseModel):
    """Flow中Edge的数据"""

    id: str = Field(description="边的ID")
    edge_from: str = Field(description="边的来源节点ID")
    edge_to: str = Field(description="边的目标节点ID")
    edge_type: EdgeType | None = Field(description="边的类型", default=EdgeType.NORMAL)


class Step(BaseModel):
    """Flow中Step的数据"""

    node: str = Field(description="Step的Node ID")
    type: str = Field(description="Step的类型")
    name: str = Field(description="Step的名称")
    description: str = Field(description="Step的描述")
    pos: PositionItem = Field(description="Step在画布上的位置", default=PositionItem(x=0, y=0))
    params: dict[str, Any] = Field(description="用户手动指定的Node参数", default={})


class FlowError(BaseModel):
    """Flow的错误处理节点"""

    use_llm: bool = Field(description="是否使用LLM处理错误")
    output_format: str | None = Field(description="错误处理节点的输出格式", default=None)


class Flow(BaseModel):
    """Flow（工作流）的数据格式"""

    name: str = Field(description="Flow的名称", min_length=1)
    description: str = Field(description="Flow的描述 ")
    connectivity: bool = Field(default=False, description="图的开始节点和结束节点是否联通，并且除结束节点都有出边")
    focus_point: PositionItem | None = Field(description="当前焦点节点", default=PositionItem(x=0, y=0))
    debug: bool = Field(description="是否经过调试", default=False)
    on_error: FlowError = FlowError(use_llm=True)
    steps: dict[str, Step] = Field(description="节点列表", default={})
    edges: list[Edge] = Field(description="边列表", default=[])
    notes: list[Note] = Field(description="备注列表", default=[])


class Permission(BaseModel):
    """权限配置"""

    type: PermissionType = Field(description="权限类型", default=PermissionType.PRIVATE)
    users: list[str] = Field(description="可访问的用户列表", default=[])


class MetadataBase(BaseModel):
    """
    Service或App的元数据

    注意：hash字段在save和load的时候exclude
    """

    type: MetadataType = Field(description="元数据类型")
    id: str = Field(description="元数据ID")
    icon: str = Field(description="图标", default="")
    name: str = Field(description="元数据名称")
    description: str = Field(description="元数据描述")
    version: str = Field(description="元数据版本")
    author: str = Field(description="创建者的用户名")
    author_name: str = Field(description="创建者用户名", default="", alias="authorName")
    hashes: dict[str, str] | None = Field(description="资源（App、Service等）下所有文件的hash值", default=None)


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
    oidc: ServiceApiAuthOidc | None = Field(description="OIDC鉴权配置", default=None)


class ServiceApiConfig(BaseModel):
    """Service的API配置"""

    server: str = Field(description="服务器地址", pattern=r"^(https|http)://.*$")
    auth: ServiceApiAuth | None = Field(description="API鉴权方式", default=None)


class ServiceMetadata(MetadataBase):
    """Service的元数据"""

    type: MetadataType = MetadataType.SERVICE
    api: ServiceApiConfig = Field(description="API配置")
    permission: Permission | None = Field(description="服务权限配置", default=None)


class AppFlow(BaseModel):
    """Flow的元数据；会被存储在App下面"""

    id: str
    name: str
    description: str
    enabled: bool = Field(description="是否启用", default=True)
    path: str = Field(description="Flow的路径")
    debug: bool = Field(description="调试是否成功", default=False)


class AppMetadata(MetadataBase):
    """App的元数据"""

    type: MetadataType = MetadataType.APP
    app_type: AppType = Field(default=AppType.FLOW, description="应用类型", frozen=True)
    published: bool = Field(description="是否发布", default=False)
    links: list[AppLink] = Field(description="相关链接", default=[])
    first_questions: list[str] = Field(description="首次提问", default=[])
    llm_id: str = Field(description="大模型ID", default="empty")
    history_len: int = Field(description="对话轮次", default=3, le=10)
    permission: Permission | None = Field(description="应用权限配置", default=None)
    flows: list[AppFlow] = Field(description="Flow列表", default=[])


class ServiceApiSpec(BaseModel):
    """外部服务API信息"""

    name: str = Field(description="OpenAPI文件名")
    description: str = Field(description="OpenAPI中关于API的Summary")
    size: int = Field(description="OpenAPI文件大小（单位：KB）")
    path: str = Field(description="OpenAPI文件路径")
    hash: str = Field(description="OpenAPI文件的hash值")


class FlowConfig(BaseModel):
    """Flow的配置信息 用于前期调试使用"""

    flow_id: str
    flow_config: Flow
