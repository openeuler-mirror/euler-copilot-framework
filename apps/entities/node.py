"""Node实体类"""
from typing import Any, Optional

from pydantic import BaseModel, Field

from apps.entities.pool import NodePool


class APINodeInput(BaseModel):
    """API节点覆盖输入"""

    param_schema: Optional[dict[str, Any]] = Field(description="API节点输入参数Schema", default=None)
    body_schema: Optional[dict[str, Any]] = Field(description="API节点输入请求体Schema", default=None)

class APINodeOutput(BaseModel):
    """API节点覆盖输出"""

    resp_schema: Optional[dict[str, Any]] = Field(description="API节点输出Schema", default=None)


class APINode(NodePool):
    """API节点"""

    call_id: str = "API"
    override_input: Optional[APINodeInput] = Field(description="API节点输入覆盖", default=None)
    override_output: Optional[APINodeOutput] = Field(description="API节点输出覆盖", default=None)


