from enum import StrEnum
from typing import Any


class VariableType(StrEnum):
    """变量类型枚举"""
    # 基础类型
    NUMBER = "number"
    STRING = "string"
    BOOLEAN = "boolean"
    OBJECT = "object"
    SECRET = "secret"
    GROUP = "group"
    FILE = "file"

    # 数组类型
    ARRAY = "array"
    ARRAY_ANY = "array[any]"
    ARRAY_STRING = "array[string]"
    ARRAY_NUMBER = "array[number]"
    ARRAY_OBJECT = "array[object]"
    ARRAY_FILE = "array[file]"
    ARRAY_BOOLEAN = "array[boolean]"
    ARRAY_SECRET = "array[secret]"

    def is_array_type(self) -> bool:
        """检查是否为数组类型"""
        return self in _ARRAY_TYPES

    def is_secret_type(self) -> bool:
        """检查是否为密钥类型"""
        return self in _SECRET_TYPES

    def get_array_element_type(self) -> "VariableType | None":
        """获取数组元素类型"""
        if not self.is_array_type():
            return None

        element_type_map = {
            VariableType.ARRAY: None,  # 未指定元素类型
            VariableType.ARRAY_ANY: None,  # any类型无法确定具体元素类型
            VariableType.ARRAY_STRING: VariableType.STRING,
            VariableType.ARRAY_NUMBER: VariableType.NUMBER,
            VariableType.ARRAY_OBJECT: VariableType.OBJECT,
            VariableType.ARRAY_FILE: VariableType.FILE,
            VariableType.ARRAY_BOOLEAN: VariableType.BOOLEAN,
            VariableType.ARRAY_SECRET: VariableType.SECRET,
        }
        return element_type_map.get(self)

    @staticmethod
    def juge_list_type(value: list[Any]) -> "VariableType":
        """判断列表的变量类型"""
        if all(isinstance(item, str) for item in value):
            return VariableType.ARRAY_STRING
        elif all(isinstance(item, (int, float)) for item in value):
            return VariableType.ARRAY_NUMBER
        elif all(isinstance(item, dict) for item in value):
            return VariableType.ARRAY_OBJECT
        elif all(isinstance(item, bool) for item in value):
            return VariableType.ARRAY_BOOLEAN
        elif all(isinstance(item, bytes) for item in value):
            return VariableType.ARRAY_FILE
        else:
            return VariableType.ARRAY_ANY

    @staticmethod
    def judge_type_by_value(value: Any) -> "VariableType":
        """根据值获取变量类型"""
        if isinstance(value, bool):
            return VariableType.BOOLEAN
        elif isinstance(value, int) or isinstance(value, float):
            return VariableType.NUMBER
        elif isinstance(value, str):
            return VariableType.STRING
        elif isinstance(value, list):
            return VariableType.juge_list_type(value)
        elif isinstance(value, dict):
            return VariableType.OBJECT
        else:
            return VariableType.STRING  # 默认使用字符串类型


class VariableScope(StrEnum):
    """变量作用域枚举"""
    SYSTEM = "system"      # 系统级变量（只读）
    USER = "user"          # 用户级变量（跟随用户）
    ENVIRONMENT = "env"    # 环境级变量（跟随flow）
    CONVERSATION = "conversation"  # 对话级变量（每次运行重新初始化）


# 数组类型集合
_ARRAY_TYPES = frozenset([
    VariableType.ARRAY,
    VariableType.ARRAY_ANY,
    VariableType.ARRAY_STRING,
    VariableType.ARRAY_NUMBER,
    VariableType.ARRAY_OBJECT,
    VariableType.ARRAY_FILE,
    VariableType.ARRAY_BOOLEAN,
    VariableType.ARRAY_SECRET,
])

# 密钥类型集合
_SECRET_TYPES = frozenset([
    VariableType.SECRET,
    VariableType.ARRAY_SECRET,
])
