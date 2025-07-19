# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""工作流变量管理模块

这个模块提供了完整的变量管理功能，包括：
- 多种变量类型支持（String、Number、Boolean、Object、Secret、File、Array等）
- 四种作用域支持（系统级、用户级、环境级、对话级）
- 变量解析和模板替换
- 安全的密钥变量处理
- 与工作流调度器的集成
"""

from .type import VariableType, VariableScope
from .base import BaseVariable, VariableMetadata
from .variables import (
    StringVariable,
    NumberVariable,
    BooleanVariable,
    ObjectVariable,
    SecretVariable,
    FileVariable,
    ArrayVariable,
    create_variable,
    VARIABLE_CLASS_MAP,
)
from .pool import VariablePool, get_variable_pool
from .parser import VariableParser, VariableReferenceBuilder, VariableContext
from .integration import VariableIntegration

__all__ = [
    # 基础类型和枚举
    "VariableType",
    "VariableScope",
    "VariableMetadata",
    "BaseVariable",
    
    # 具体变量类型
    "StringVariable",
    "NumberVariable",
    "BooleanVariable",
    "ObjectVariable",
    "SecretVariable",
    "FileVariable",
    "ArrayVariable",
    
    # 工厂函数和映射
    "create_variable",
    "VARIABLE_CLASS_MAP",
    
    # 变量池
    "VariablePool",
    "get_variable_pool",
    
    # 解析器
    "VariableParser",
    "VariableReferenceBuilder",
    "VariableContext",
    
    # 集成功能
    "VariableIntegration",
]
