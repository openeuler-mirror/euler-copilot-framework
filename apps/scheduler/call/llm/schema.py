# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""LLM工具的输入输出定义"""

from pydantic import Field

from apps.scheduler.call.core import DataBase


class LLMInput(DataBase):
    """定义LLM工具调用的输入"""

    message: list[dict[str, str]] = Field(description="输入给大模型的消息列表")


class LLMOutput(DataBase):
    """定义LLM工具调用的输出"""

    reply: str = Field(description="定义LLM工具调用的输出")