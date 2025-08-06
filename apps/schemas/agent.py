# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""agent 相关数据结构"""

from pydantic import Field

from apps.schemas.enum_var import (
    AppType,
    MetadataType,
)
from apps.schemas.flow import MetadataBase, Permission


class AgentAppMetadata(MetadataBase):
    """智能体App的元数据"""

    type: MetadataType = MetadataType.APP
    app_type: AppType = Field(default=AppType.AGENT, description="应用类型", frozen=True)
    published: bool = Field(description="是否发布", default=False)
    history_len: int = Field(description="对话轮次", default=3, le=10)
    mcp_service: list[str] = Field(default=[], description="MCP服务id列表")
    llm_id: str = Field(default="empty", description="大模型ID")
    permission: Permission | None = Field(description="应用权限配置", default=None)
    version: str = Field(description="元数据版本")
