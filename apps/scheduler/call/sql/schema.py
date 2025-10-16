# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""SQL工具的输入输出"""

from typing import Any, Optional

from pydantic import Field

from apps.scheduler.call.core import DataBase


class SQLInput(DataBase):
    """SQL工具的输入"""

    question: str = Field(description="用户输入")


class SQLOutput(DataBase):
    """SQL工具的输出"""

    result: list[dict[str, Any]] = Field(description="SQL工具的执行结果")
    sql: str = Field(description="SQL语句")
