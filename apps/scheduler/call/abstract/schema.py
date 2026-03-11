# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""摘要工具的输入和输出"""

from pydantic import Field

from apps.scheduler.call.core import DataBase


class AbstractOutput(DataBase):
    """摘要工具的输出"""

    abstract: str = Field(description="对问答上下文的摘要内容")
