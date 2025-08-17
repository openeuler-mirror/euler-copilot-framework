# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 相关数据结构"""

import uuid
from enum import Enum
from typing import Any

from lancedb.pydantic import LanceModel, Vector
from pydantic import BaseModel, Field


class MCPInstallStatus(str, Enum):
    """MCP 服务状态"""
    INIT = "init"
    INSTALLING = "installing"
    CANCELLED = "cancelled"
    READY = "ready"
    FAILED = "failed"


class MCPStatus(str, Enum):
    """MCP 状态"""

    UNINITIALIZED = "uninitialized"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class MCPType(str, Enum):
    """MCP 类型"""

    SSE = "sse"
    STDIO = "stdio"
    STREAMABLE = "stream"


class MCPBasicConfig(BaseModel):
    """MCP 基本配置"""

    env: dict[str, str] = Field(description="MCP 服务器环境变量", default={})
    auto_approve: list[str] = Field(description="自动批准的MCP工具ID列表", default=[], alias="autoApprove")
    disabled: bool = Field(description="MCP 服务器是否禁用", default=False)
    auto_install: bool = Field(description="是否自动安装MCP服务器", default=True)
    timeout: int = Field(description="MCP 服务器超时时间（秒）", default=60, alias="timeout")
    description: str = Field(description="MCP 服务器自然语言描述", default="")
    headers: dict[str, str] = Field(description="MCP 服务器请求头", default={}, alias="headers")


class MCPServerStdioConfig(MCPBasicConfig):
    """MCP 服务器配置"""

    command: str = Field(description="MCP 服务器命令")
    args: list[str] = Field(description="MCP 服务器命令参数")


class MCPServerSSEConfig(MCPBasicConfig):
    """MCP 服务器配置"""

    url: str = Field(description="MCP 服务器地址", default="")


class MCPServerConfig(BaseModel):
    """MCP 服务器配置"""

    name: str = Field(description="MCP 服务器自然语言名称", default="")
    overview: str = Field(description="MCP 服务器概述", default="")
    description: str = Field(description="MCP 服务器自然语言描述", default="")
    type: MCPType = Field(description="MCP 服务器类型", default=MCPType.STDIO)
    author: str = Field(description="MCP 服务器上传者", default="")
    config: MCPServerStdioConfig | MCPServerSSEConfig = Field(description="MCP 服务器配置")


class MCPTool(BaseModel):
    """MCP工具"""

    id: str = Field(description="MCP工具ID")
    name: str = Field(description="MCP工具名称")
    description: str = Field(description="MCP工具描述")
    mcp_id: str = Field(description="MCP ID")
    input_schema: dict[str, Any] = Field(description="MCP工具输入参数")


class MCPCollection(BaseModel):
    """MCP相关信息，存储在MongoDB的 ``mcp`` 集合中"""

    id: str = Field(description="MCP ID", alias="_id", default="")
    name: str = Field(description="MCP 自然语言名称", default="")
    description: str = Field(description="MCP 自然语言描述", default="")
    type: MCPType = Field(description="MCP 类型", default=MCPType.SSE)
    activated: list[str] = Field(description="激活该MCP的用户ID列表", default=[])
    tools: list[MCPTool] = Field(description="MCP工具列表", default=[])
    status: MCPInstallStatus = Field(description="MCP服务状态", default=MCPInstallStatus.INIT)
    author: str = Field(description="MCP作者", default="")


class MCPVector(LanceModel):
    """MCP向量化数据，存储在LanceDB的 ``mcp`` 表中"""

    id: str = Field(description="MCP ID")
    embedding: Vector(dim=1024) = Field(description="MCP描述的向量信息")  # type: ignore[call-arg]


class MCPToolVector(LanceModel):
    """MCP工具向量化数据，存储在LanceDB的 ``mcp_tool`` 表中"""

    id: str = Field(description="工具ID")
    mcp_id: str = Field(description="MCP ID")
    embedding: Vector(dim=1024) = Field(description="MCP工具描述的向量信息")  # type: ignore[call-arg]


class GoalEvaluationResult(BaseModel):
    """MCP 目标评估结果"""

    can_complete: bool = Field(description="是否可以完成目标")
    reason: str = Field(description="评估原因")


class FlowName(BaseModel):
    """MCP 流程名称"""

    flow_name: str = Field(description="MCP 流程名称", default="")


class RestartStepIndex(BaseModel):
    """MCP重新规划的步骤索引"""

    start_index: int = Field(description="重新规划的起始步骤索引")
    reasoning: str = Field(description="重新规划的原因")


class Risk(str, Enum):
    """MCP工具风险类型"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolSkip(BaseModel):
    """MCP工具跳过执行结果"""

    skip: bool = Field(description="是否跳过当前步骤", default=False)


class ToolRisk(BaseModel):
    """MCP工具风险评估结果"""

    risk: Risk = Field(description="风险类型", default=Risk.LOW)
    reason: str = Field(description="风险原因", default="")


class ErrorType(str, Enum):
    """MCP工具错误类型"""

    MISSING_PARAM = "missing_param"
    DECORRECT_PLAN = "decorrect_plan"


class ToolExcutionErrorType(BaseModel):
    """MCP工具执行错误"""

    type: ErrorType = Field(description="错误类型", default=ErrorType.MISSING_PARAM)
    reason: str = Field(description="错误原因", default="")


class IsParamError(BaseModel):
    """MCP工具参数错误"""

    is_param_error: bool = Field(description="是否是参数错误", default=False)


class MCPSelectResult(BaseModel):
    """MCP选择结果"""

    mcp_id: str = Field(description="MCP Server的ID")


class MCPToolSelectResult(BaseModel):
    """MCP工具选择结果"""

    name: str = Field(description="工具名称")


class MCPToolIdsSelectResult(BaseModel):
    """MCP工具ID选择结果"""

    tool_ids: list[str] = Field(description="工具ID列表")


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

    tool_id: str = Field(description="工具ID")
    description: str = Field(description="步骤描述,15个字以下")
