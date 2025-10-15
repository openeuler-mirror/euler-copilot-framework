# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Choice Call的输入和输出"""
import uuid
from enum import Enum

from pydantic import Field

from apps.scheduler.call.core import DataBase
from apps.schemas.parameters import (
    BoolOperate,
    DictOperate,
    ListOperate,
    NumberOperate,
    StringOperate,
    Type,
)


class Logic(str, Enum):
    """Choice 工具支持的逻辑运算符"""

    AND = "and"
    OR = "or"


class Value(DataBase):
    """值的结构"""

    step_id: str | None = Field(description="步骤id", default=None)
    type: Type | None = Field(description="值的类型", default=None)
    name: str | None = Field(description="值的名称", default=None)
    value: str | float | int | bool | list | dict | None = Field(description="值", default=None)


class Condition(DataBase):
    """单个条件"""

    left: Value = Field(description="左值", default=Value())
    right: Value = Field(description="右值", default=Value())
    operate: NumberOperate | StringOperate | ListOperate | BoolOperate | DictOperate | None = Field(
        description="运算符", default=None)
    id: str = Field(description="条件ID", default_factory=lambda: str(uuid.uuid4()))


class ChoiceBranch(DataBase):
    """子分支"""

    branch_id: str = Field(description="分支ID", default_factory=lambda: str(uuid.uuid4()))
    logic: Logic = Field(description="逻辑运算符", default=Logic.AND)
    conditions: list[Condition] = Field(description="条件列表", default=[])
    is_default: bool = Field(description="是否为默认分支", default=True)


class ChoiceInput(DataBase):
    """Choice Call的输入"""

    choices: list[ChoiceBranch] = Field(description="分支", default=[])


class ChoiceOutput(DataBase):
    """Choice Call的输出"""

    branch_id: str = Field(description="分支ID", default="")
