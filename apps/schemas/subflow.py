# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""子工作流相关的Schema定义"""

from pydantic import BaseModel, Field


class AppSubFlow(BaseModel):
    """应用的子工作流元数据"""
    
    id: str = Field(description="子工作流ID")
    name: str = Field(description="子工作流名称")
    description: str = Field(description="子工作流描述")
    path: str = Field(description="子工作流文件路径")
    debug: bool = Field(default=False, description="是否已调试")
    parent_flow_id: str = Field(default="", description="父工作流ID")
    created_at: float = Field(default=0, description="创建时间") 