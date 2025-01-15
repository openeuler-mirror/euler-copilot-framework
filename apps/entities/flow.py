"""Flow和Service等外置配置数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field

from apps.entities.enum_var import CallType, MetadataType


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


class Service(BaseModel):
    """外部服务信息

    collection: service
    """

    id: str = Field(alias="_id")
    name: str
    description: str
    dir_path: str


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

    key: call_metadata
    """

    id: str = Field(alias="_id", description="Call的ID")
    type: CallType = Field(description="Call的类型")
    name: str = Field(description="Call的名称")
    description: str = Field(description="Call的描述")
    path: str = Field(description="Call的路径；当为系统Call时，形如 system::LLM；当为Python Call时，形如 python::tune::call.tune.CheckSystem")


class Metadata(BaseModel):
    """Service或App的元数据"""

    type: MetadataType = Field(description="元数据类型")
    id: str = Field(alias="_id", description="元数据ID")
    name: str = Field(description="元数据名称")
    description: str = Field(description="元数据描述")
    version: str = Field(description="元数据版本")
    
