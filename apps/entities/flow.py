"""App、Flow和Service等外置配置数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field

from apps.entities.enum_var import (
    AppPermissionType,
    MetadataType,
    EdgeType,
)


class NodePos(BaseModel):
    """节点在画布上的位置"""

    x: int = Field(description="节点在画布上的X坐标")
    y: int = Field(description="节点在画布上的Y坐标")

class Edge(BaseModel):
    """Flow中Edge的数据"""

    id: str = Field(description="边的ID")
    edge_from: str = Field(description="边的来源节点ID", alias="from")
    edge_to: str = Field(description="边的目标节点ID", alias="to")
    edge_type: Optional[EdgeType] = Field(description="边的类型", alias="type")


class Node(BaseModel):
    """Flow中Node的数据"""

    id: str = Field(description="节点的ID；与NodePool中的ID对应")
    name: str = Field(description="节点名称")
    description: str = Field(description="节点描述")
    pos: NodePos = Field(description="节点在画布上的位置", default=NodePos(x=0, y=0))
    params: dict[str, Any] = Field(description="用户手动指定的节点参数", default={})


class NextFlow(BaseModel):
    """Flow中“下一步”的数据格式"""

    flow_id: str
    question: Optional[str] = None


class FlowError(BaseModel):
    """Flow的错误处理节点"""

    use_llm: bool = Field(description="是否使用LLM处理错误")
    output_format: Optional[str] = Field(description="错误处理节点的输出格式")


class Flow(BaseModel):
    """Flow（工作流）的数据格式"""
    
    name: str = Field(description="Flow的名称")
    description: str = Field(description="Flow的描述")
    on_error: FlowError = FlowError(use_llm=True)
    nodes: list[Node] = Field(description="节点列表", default=[])
    edges: list[Edge] = Field(description="边列表", default=[])
    next_flow: Optional[list[NextFlow]] = None


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


class AppLink(BaseModel):
    """App的相关链接"""

    title: str = Field(description="链接标题")
    url: str = Field(description="链接URL")


class AppPermission(BaseModel):
    """App的权限配置"""

    type: AppPermissionType = Field(description="权限类型", default=AppPermissionType.PRIVATE)
    users: list[str] = Field(description="可访问的用户列表", default=[])


class AppMetadata(MetadataBase):
    """App的元数据"""

    type: MetadataType = MetadataType.APP
    links: list[AppLink] = Field(description="相关链接", default=[])
    first_questions: list[str] = Field(description="首次提问", default=[])
    history_len: int = Field(description="对话轮次", default=3, le=10)
    permissions: Optional[AppPermission] = Field(description="应用权限配置", default=None)


class ServiceApiSpec(BaseModel):
    """外部服务API信息"""

    name: str = Field(description="OpenAPI文件名")
    description: str = Field(description="OpenAPI中关于API的Summary")
    size: int = Field(description="OpenAPI文件大小（单位：KB）")
    path: str = Field(description="OpenAPI文件路径")
    hash: str = Field(description="OpenAPI文件的hash值")

class PositionItem(BaseModel):
    """请求/响应中的前端相对位置变量类"""
    x:float
    y:float
class FlowItem(BaseModel):
    """请求/响应中的流变量类"""
    flow_id:str=Optional[Field](alias="flowId")
    name:str
    description:str
    enable:bool
    created_at: str= Field(alias="createdAt")
class BranchItem(BaseModel):
    """请求/响应中的节点分支变量类"""
    branch_id:str=Field(alias="branchId")
    type:str
    description:str
class DependencyItem(BaseModel):
    """请求/响应中的节点依赖变量类"""
    node_id:str=Field(alias="nodeId")
    type:str
class NodeItem(BaseModel):
    """请求/响应中的节点变量类"""
    node_id:str=Field(alias="nodeId")
    api_id:str=Field(alias="apiId")
    name:str
    type:str
    description:str
    enable:str
    branches:list[BranchItem]
    depedency:DependencyItem
    position:PositionItem
    editable:bool
    created_at: str= Field(alias="createdAt")
class EdgeItem(BaseModel):
    """请求/响应中的边变量类"""
    egde_id:str=Field(alias="edgeId")
    source_node:str=Field(alias="sourceNode")
    target_node:str=Field(alias="targetNode")
    type:str
    branch_id:str=Field(alias="branchId")
    created_at: str= Field(alias="createdAt")