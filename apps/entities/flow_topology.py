"""前端展示flow用到的数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, Optional
from typing import Optional

from pydantic import BaseModel, Field

from apps.entities.enum_var import EdgeType, NodeType

class NodeMetaDataItem(BaseModel):
    """节点元数据类"""
    node_meta_data_id: str = Field(alias="nodeMetaDataId")
    type: str
    name: str
    description: str
    parameters: Optional[dict[str, Any]]
    editable: bool = Field(default=True)
    created_at: Optional[float] = Field(alias="createdAt")

class NodeServiceItem(BaseModel):
    """GET /api/flow/service 中单个service信息以及service下的节点元数据的信息"""
    service_id: str = Field(..., alias="serviceId", description="服务ID")
    name: str = Field(..., description="服务名称")
    type: str = Field(..., description="服务类型")
    node_meta_datas: list[NodeMetaDataItem] = Field(alias="nodeMetaDatas", default=[])
    created_at: str = Field(..., alias="createdAt", description="创建时间")
class PositionItem(BaseModel):
    """请求/响应中的前端相对位置变量类"""
    x: float = Field(default=0.0)
    y: float = Field(default=0.0)


class DependencyItem(BaseModel):
    """请求/响应中的节点依赖变量类"""
    node_id: str = Field(alias="nodeId")
    type: str


class NodeItem(BaseModel):
    """请求/响应中的节点变量类"""
    node_id: str = Field(alias="nodeId",default="")
    service_id: str = Field(alias="serviceId",default="")
    node_meta_data_id: str = Field(alias="nodeMetaDataId",default="")
    name: str=Field(default="")
    type: str = Field(default=NodeType.NORMAL.value)
    description: str = Field(default='')
    enable: bool = Field(default=True)
    parameters: dict[str, Any] = Field(default={})
    depedency: Optional[DependencyItem] = None
    position: PositionItem=Field(default=PositionItem())
    editable: bool = Field(default=True)


class EdgeItem(BaseModel):
    """请求/响应中的边变量类"""
    edge_id: str = Field(alias="edgeId")
    source_node: str = Field(alias="sourceNode")
    target_node: str = Field(alias="targetNode")
    type: str = Field(default=EdgeType.NORMAL.value)
    branch_id: str = Field(alias="branchId")


class FlowItem(BaseModel):
    """请求/响应中的流变量类"""
    flow_id: Optional[str] = Field(alias="flowId", default='flow id')
    name: str = Field(default='flow name')
    description: str = Field(default='flow description')
    enable: bool = Field(default=True)
    editable: bool = Field(default=True)
    nodes: list[NodeItem] = Field(default=[])
    edges: list[EdgeItem] = Field(default=[])
    created_at: Optional[float] = Field(alias="createdAt", default=0)
