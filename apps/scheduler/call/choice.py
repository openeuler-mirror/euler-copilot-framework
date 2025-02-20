"""工具：使用大模型或使用程序做出判断

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from enum import Enum

from pydantic import BaseModel


class Operator(str, Enum):
    """Choice工具支持的运算符"""

    pass


class ChoiceInput(BaseModel):
    """Choice工具的输入格式"""

    pass

