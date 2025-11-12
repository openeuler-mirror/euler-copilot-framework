from enum import StrEnum


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
