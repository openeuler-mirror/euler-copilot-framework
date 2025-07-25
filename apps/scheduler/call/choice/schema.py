# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Choice Call的输入和输出"""

from enum import Enum

from pydantic import BaseModel, Field

from apps.scheduler.call.core import DataBase
class Operator(str, Enum):
    """Choice Call支持的运算符"""

    EQUAL = "equal"
    NEQUAL = "not_equal"
    GREAT = "great"
    GREAT_EQUALS = "great_equals"
    LESS = "less"
    LESS_EQUALS = "less_equals"
    # string
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    GREATER = "greater"
    GREATER_EQUALS = "greater_equals"
    SMALLER = "smaller"
    SMALLER_EQUALS = "smaller_equals"
    # bool
    IS_EMPTY = "is_empty"
    NOT_EMPTY = "not_empty"


class Logic(str, Enum):
    """Choice 工具支持的逻辑运算符"""

    AND = "and"
    OR = "or"


class Type(str, Enum):
    """Choice 工具支持的类型"""

    STRING = "string"
    INT = "int"
    BOOL = "bool"


class Value(BaseModel):
    """值的结构"""

    step_id: str = Field(description="步骤id", default="")
    value: str | int | bool = Field(description="值", default=None)


class Condition(BaseModel):
    """单个条件"""

    type: Type = Field(description="值的类型", default=Type.STRING)
    left: Value = Field(description="左值")
    right: Value = Field(description="右值")
    operator: Operator = Field(description="运算符", default="equal")
    id: int = Field(description="条件ID")


class ChoiceBranch(BaseModel):
    """子分支"""

    branch_id: str = Field(description="分支ID", default="")
    logic: Logic = Field(description="逻辑运算符", default=Logic.AND)
    conditions: list[Condition] = Field(description="条件列表", default=[])
    is_default: bool = Field(description="是否为默认分支", default=False)


class ChoiceInput(DataBase):
    """Choice Call的输入"""

    choices: list[ChoiceBranch] = Field(description="分支", default=[])


class ChoiceOutput(DataBase):
    """Choice Call的输出"""
