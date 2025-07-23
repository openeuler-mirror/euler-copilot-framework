# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""前端展示flow用到的数据结构"""

from typing import Any

from pydantic import BaseModel, Field

from apps.schemas.enum_var import CallType, EdgeType


class NodeMetaDataItem(BaseModel):
    """节点元数据类"""

    node_id: str = Field(alias="nodeId")
    call_id: str = Field(alias="callId")
    name: str
    type: CallType
    description: str
    parameters: dict[str, Any] | None
    editable: bool = Field(default=True)
    created_at: float | None = Field(alias="createdAt")


class NodeServiceItem(BaseModel):
    """GET /api/flow/service 中单个service信息以及service下的节点元数据的信息"""

    service_id: str = Field(..., alias="serviceId", description="服务ID")
    name: str = Field(..., description="服务名称")
    type: str = Field(..., description="服务类型")
    node_meta_datas: list[NodeMetaDataItem] = Field(alias="nodeMetaDatas", default=[])
    created_at: str | None = Field(default=None, alias="createdAt", description="创建时间")


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

    step_id: str = Field(alias="stepId", default="")
    service_id: str = Field(alias="serviceId", default="")
    node_id: str = Field(alias="nodeId", default="")
    name: str = Field(default="")
    call_id: str = Field(alias="callId", default="Empty")
    description: str = Field(default="")
    enable: bool = Field(default=True)
    parameters: dict[str, Any] = Field(default={})
    depedency: DependencyItem | None = None
    position: PositionItem = Field(default=PositionItem())
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

    flow_id: str | None = Field(alias="flowId", default="工作流ID")
    name: str = Field(default="工作流名称")
    description: str = Field(default="工作流描述")
    enable: bool = Field(default=True)
    editable: bool = Field(default=True)
    nodes: list[NodeItem] = Field(default=[])
    edges: list[EdgeItem] = Field(default=[])
    created_at: float | None = Field(alias="createdAt", default=0)
    connectivity: bool = Field(default=False,description="图的开始节点和结束节点是否联通，并且除结束节点都有出边")
    focus_point: PositionItem = Field(alias="focusPoint", default=PositionItem())
    debug: bool = Field(default=False)
