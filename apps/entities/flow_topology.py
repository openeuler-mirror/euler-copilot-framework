"""前端展示flow用到的数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, Optional
from typing import Optional

from pydantic import BaseModel, Field

from apps.entities.enum_var import EdgeType, NodeType


class ServiceItem(BaseModel):
    """元数据归属的服务类"""
    service_id: str = Field(alias="serviceId")
    name: str
    type: str
    created_at: Optional[float] = Field(alias="createdAt")


class NodeMetaDataItem(BaseModel):
    """节点元数据类"""
    api_id: str = Field(alias="apiId")
    name: str
    type: str
    description: str
    parameters_template: str = Field(alias="parametersTemplate")
    editable: bool = Field(default=True)
    created_at: Optional[float] = Field(alias="createdAt")


class PositionItem(BaseModel):
    """请求/响应中的前端相对位置变量类"""
    x: float
    y: float


class DependencyItem(BaseModel):
    """请求/响应中的节点依赖变量类"""
    node_id: str = Field(alias="nodeId")
    type: str


class NodeItem(BaseModel):
    """请求/响应中的节点变量类"""
    node_id: str = Field(alias="nodeId")
    api_id: str = Field(alias="apiId")
    name: str
    type: str = Field(default=NodeType.NORMAL.value)
    description: str = Field(default='')
    enable: str = Field(default=True)
    parameters: dict[str, Any]
    depedency: Optional[DependencyItem] = None
    position: PositionItem
    editable: bool = Field(default=True)
    created_at: Optional[float] = Field(alias="createdAt")


class EdgeItem(BaseModel):
    """请求/响应中的边变量类"""
    edge_id: str = Field(alias="edgeId")
    source_node: str = Field(alias="sourceNode")
    target_node: str = Field(alias="targetNode")
    type: str = Field(default=EdgeType.NORMAL.value)
    branch_id: str = Field(alias="branchId")
    created_at: Optional[float] = Field(alias="createdAt")


class FlowItem(BaseModel):
    """请求/响应中的流变量类"""
    flow_id: Optional[str] = Field(alias="flowId")
    name: str
    description: str
    enable: bool = Field(default=True)
    editable: bool = Field(default=True)
    created_at: Optional[float] = Field(alias="createdAt")
    nodes: list[NodeItem]
    edeges: list[EdgeItem]
