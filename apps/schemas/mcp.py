# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 相关数据结构"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from apps.models.mcp import MCPType


class MCPStatus(str, Enum):
    """MCP 状态"""

    UNINITIALIZED = "uninitialized"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class MCPContext(BaseModel):
    """MCP执行上下文"""

    step_description: str
    """步骤描述"""
    input_data: dict[str, Any]
    """输入数据"""
    output_data: dict[str, Any]
    """输出数据"""


class MCPBasicConfig(BaseModel):
    """MCP 基本配置"""

    autoApprove: list[str] = Field(description="自动批准的MCP权限列表", default=[])  # noqa: N815
    autoInstall: bool = Field(description="是否自动安装MCP服务器", default=True)  # noqa: N815
    timeout: int = Field(description="MCP 服务器超时时间（秒）", default=60, alias="timeout")


class MCPServerStdioConfig(MCPBasicConfig):
    """MCP 服务器配置"""

    env: dict[str, Any] = Field(description="MCP 服务器环境变量", default={})
    command: str = Field(description="MCP 服务器命令")
    args: list[str] = Field(description="MCP 服务器命令参数")


class MCPServerSSEConfig(MCPBasicConfig):
    """MCP 服务器配置"""

    url: str = Field(description="MCP 服务器地址", default="http://example.com/sse", pattern=r"^https?://.*$")
    headers: dict[str, Any] = Field(description="MCP 服务器请求头", default={})


class MCPServerItem(BaseModel):
    """MCP 服务器信息"""

    mcpServers: dict[str, MCPServerStdioConfig | MCPServerSSEConfig] = Field( # noqa: N815
        description="MCP 服务器列表",
        max_length=1,
        min_length=1,
    )


class MCPServerConfig(MCPServerItem):
    """MCP 服务器配置"""

    name: str = Field(description="MCP 服务器自然语言名称", default="")
    overview: str = Field(description="MCP 服务器概述", default="")
    description: str = Field(description="MCP 服务器自然语言描述", default="")
    mcpType: MCPType = Field(description="MCP 服务器类型", default=MCPType.STDIO)  # noqa: N815
    author: str = Field(description="MCP 服务器上传者", default="")


class Risk(str, Enum):
    """MCP工具风险类型"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class ToolRisk(BaseModel):
    """MCP工具风险评估结果"""

    risk: Risk = Field(description="风险类型", default=Risk.LOW)
    reason: str = Field(description="风险原因", default="")


class IsParamError(BaseModel):
    """MCP工具参数错误"""

    is_param_error: bool = Field(description="是否是参数错误", default=False)


class MCPSelectResult(BaseModel):
    """MCP选择结果"""

    mcp_id: str = Field(description="MCP Server的ID")


class MCPPlanItem(BaseModel):
    """MCP 计划"""

    step_id: str = Field(description="步骤的ID", default="")
    content: str = Field(description="计划内容")
    tool: str = Field(description="工具名称")
    instruction: str = Field(description="工具指令")


class MCPPlan(BaseModel):
    """MCP 计划"""

    plans: list[MCPPlanItem] = Field(description="计划列表", default=[])


class Step(BaseModel):
    """MCP步骤"""

    tool_name: str = Field(description="工具名称")
    description: str = Field(description="步骤描述")


class MCPRiskConfirm(BaseModel):
    """MCP工具风险确认"""

    confirm: bool = Field(description="是否确认")


class UpdateMCPServiceRequest(BaseModel):
    """POST /api/mcpservice 请求数据结构"""

    mcp_id: str = Field(alias="mcpId", description="MCP服务ID（更新时传递）")
    name: str = Field(..., description="MCP服务名称")
    description: str = Field(..., description="MCP服务描述")
    overview: str = Field(..., description="MCP服务概述")
    config: dict[str, Any] = Field(..., description="MCP服务配置")
    mcp_type: MCPType = Field(description="MCP传输协议(Stdio/SSE/Streamable)", default=MCPType.STDIO, alias="mcpType")


class ActiveMCPServiceRequest(BaseModel):
    """POST /api/mcp/{serviceId} 请求数据结构"""

    active: bool = Field(description="是否激活mcp服务")
    mcp_env: dict[str, Any] | None = Field(default=None, description="MCP服务环境变量", alias="mcpEnv")
