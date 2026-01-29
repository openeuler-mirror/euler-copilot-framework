# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型返回的chunk"""

from typing import Any

from pydantic import BaseModel, Field


class LLMToolCall(BaseModel):
    """大模型工具调用"""

    id: str = Field(description="工具调用ID")
    name: str = Field(description="工具名称")
    arguments: dict[str, Any] = Field(description="工具参数")


class LLMChunk(BaseModel):
    """大模型返回的chunk"""

    reasoning_content: str | None = None
    content: str | None = None
    tool_call: list[LLMToolCall] | None = None


class LLMFunctions(BaseModel):
    """大模型可选调用的函数"""

    name: str = Field(description="函数名称")
    description: str = Field(description="函数描述")
    param_schema: dict[str, Any] = Field(description="函数参数的JSON Schema")
