# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""DirectReply工具的输入输出定义"""

from pydantic import Field

from apps.scheduler.call.core import DataBase


class DirectReplyInput(DataBase):
    """定义DirectReply工具调用的输入"""

    answer: str = Field(description="直接回复的内容，支持变量引用语法")


class DirectReplyOutput(DataBase):
    """定义DirectReply工具调用的输出"""

    message: str = Field(description="处理后的回复消息") 