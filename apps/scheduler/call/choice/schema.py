# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Choice Call的输入和输出"""
import uuid

from enum import Enum

from pydantic import BaseModel, Field

from apps.schemas.parameters import (
    NumberOperate,
    StringOperate,
    ListOperate,
    BoolOperate,
    DictOperate,
    ValueType,
)
from apps.scheduler.call.core import DataBase
from apps.scheduler.variable.type import VariableType


class Logic(str, Enum):
    """Choice 工具支持的逻辑运算符"""

    AND = "and"
    OR = "or"


class Value(DataBase):
    """值的结构"""

    type: ValueType | None = Field(description="值的类型", default=None)
    value: str | float | int | bool | list | dict | None = Field(description="值", default=None)


class Condition(DataBase):
    """单个条件"""

    left: Value = Field(description="左值", default=Value())
    right: Value = Field(description="右值", default=Value())
    operator: NumberOperate | StringOperate | ListOperate | BoolOperate | DictOperate | None = Field(
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


def convert_variable_type_to_value_type(var_type: VariableType) -> ValueType | None:
    """将VariableType转换为ValueType
    
    Args:
        var_type: 变量类型
        
    Returns:
        ValueType: 对应的值类型，如果无法转换则返回None
    """
    
    type_mapping = {
        VariableType.STRING: ValueType.STRING,
        VariableType.NUMBER: ValueType.NUMBER,
        VariableType.BOOLEAN: ValueType.BOOL,
        VariableType.OBJECT: ValueType.DICT,
        VariableType.ARRAY_ANY: ValueType.LIST,
        VariableType.ARRAY_STRING: ValueType.LIST,
        VariableType.ARRAY_NUMBER: ValueType.LIST,
        VariableType.ARRAY_OBJECT: ValueType.LIST,
        VariableType.ARRAY_FILE: ValueType.LIST,
        VariableType.ARRAY_BOOLEAN: ValueType.LIST,
        VariableType.ARRAY_SECRET: ValueType.LIST,
    }
    
    return type_mapping.get(var_type)
