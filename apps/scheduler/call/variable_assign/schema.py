# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""变量赋值Call的Schema定义"""

from typing import Any, List, Optional
from enum import StrEnum

from pydantic import Field

from apps.scheduler.call.core import DataBase


class StringOperation(StrEnum):
    """字符串类型变量操作枚举"""
    OVERWRITE = "overwrite"  # 覆盖
    CLEAR = "clear"         # 清空


class NumberOperation(StrEnum):
    """数值类型变量操作枚举"""
    OVERWRITE = "overwrite"  # 覆盖
    ADD = "add"             # 加法
    SUBTRACT = "subtract"   # 减法
    MULTIPLY = "multiply"   # 乘法
    DIVIDE = "divide"       # 除法
    MODULO = "modulo"       # 求余
    POWER = "power"         # 乘幂
    SQRT = "sqrt"           # 开方
    CLEAR = "clear"         # 清空


class ArrayOperation(StrEnum):
    """数组类型变量操作枚举"""
    OVERWRITE = "overwrite"     # 覆盖
    CLEAR = "clear"            # 清空
    APPEND = "append"          # 追加单个元素
    EXTEND = "extend"          # 扩展（追加多个元素）
    POP_FIRST = "pop_first"    # 移除首项
    POP_LAST = "pop_last"      # 移除尾项


class VariableOperation(DataBase):
    """单个变量操作定义"""
    variable_name: str = Field(description="要操作的变量名称")
    operation: str = Field(description="操作类型")
    value: Any = Field(description="操作值（某些操作不需要此参数）", default=None)
    variable_type: Optional[str] = Field(description="变量类型", default=None)
    is_value_reference: Optional[bool] = Field(description="值是否为变量引用", default=False)


class VariableAssignInput(DataBase):
    """变量赋值输入参数"""
    
    operations: Optional[List[VariableOperation]] = Field(
        description="变量操作列表", 
        default=None
    )


class VariableAssignOutput(DataBase):
    """变量赋值输出结果（实际不使用）"""
    pass
