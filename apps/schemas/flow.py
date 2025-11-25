# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""App、Flow和Service等外置配置数据结构"""

import uuid
from typing import Any

from pydantic import BaseModel, Field

from apps.models import AppType, PermissionType

from .appcenter import AppLink
from .enum_var import EdgeType, MetadataType
from .flow_topology import FlowBasicConfig, FlowCheckStatus, FlowItem, PositionItem
from .response_data import ResponseData


class Edge(BaseModel):
    """Flow中Edge的数据"""

    id: uuid.UUID = Field(description="边的ID")
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
    description: str = Field(description="Flow的描述")
    checkStatus: FlowCheckStatus = Field(description="Flow的配置检查状态")  # noqa: N815
    basicConfig: FlowBasicConfig = Field(description="Flow的基本配置")  # noqa: N815
    onError: FlowError = FlowError(use_llm=True)  # noqa: N815
    steps: dict[uuid.UUID, Step] = Field(description="节点列表", default={})
    edges: list[Edge] = Field(description="边列表", default=[])


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
    id: uuid.UUID = Field(description="元数据ID")
    name: str = Field(description="元数据名称")
    description: str = Field(description="元数据描述")
    author: str = Field(description="创建者的用户名")
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

    id: uuid.UUID = Field(description="Service的ID")
    type: MetadataType = MetadataType.SERVICE
    api: ServiceApiConfig = Field(description="API配置")
    permission: Permission | None = Field(description="服务权限配置", default=None)


class AppFlow(BaseModel):
    """Flow的元数据；会被存储在App下面"""

    id: uuid.UUID
    name: str
    description: str
    enabled: bool = Field(description="是否启用", default=True)
    path: str = Field(description="Flow的路径")
    debug: bool = Field(description="调试是否成功", default=False)


class AppMetadataBase(MetadataBase):
    """App的基础元数据（智能体和Flow应用的公共部分）"""

    type: MetadataType = MetadataType.APP
    app_type: AppType = Field(description="应用类型", frozen=True)
    published: bool = Field(description="是否发布", default=False)
    links: list[AppLink] = Field(description="相关链接", default=[])
    first_questions: list[str] = Field(description="首次提问", default=[])
    history_len: int = Field(description="对话轮次", default=3, le=10)
    permission: Permission | None = Field(description="应用权限配置", default=None)


class AgentAppMetadata(AppMetadataBase):
    """智能体App的元数据"""

    app_type: AppType = Field(default=AppType.AGENT, description="应用类型", frozen=True)
    mcp_service: list[str] = Field(default=[], description="MCP服务id列表")


class FlowAppMetadata(AppMetadataBase):
    """Flow App的元数据"""

    app_type: AppType = Field(default=AppType.FLOW, description="应用类型", frozen=True)
    flows: list[AppFlow] = Field(description="Flow列表", default=[])


class FlowStructureGetMsg(BaseModel):
    """GET /api/flow result"""

    flow: FlowItem = Field(default=FlowItem())


class FlowStructureGetRsp(ResponseData):
    """GET /api/flow 返回数据结构"""

    result: FlowStructureGetMsg


class FlowStructurePutMsg(BaseModel):
    """PUT /api/flow result"""

    flow: FlowItem = Field(default=FlowItem())


class FlowStructurePutRsp(ResponseData):
    """PUT /api/flow 返回数据结构"""

    result: FlowStructurePutMsg


class FlowStructureDeleteMsg(BaseModel):
    """DELETE /api/flow/ result"""

    flow_id: str = Field(alias="flowId", default="")


class FlowStructureDeleteRsp(ResponseData):
    """DELETE /api/flow/ 返回数据结构"""

    result: FlowStructureDeleteMsg
    flows: list[AppFlow] = Field(description="Flow列表", default=[])
