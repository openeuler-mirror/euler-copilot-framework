from enum import Enum


class NumberOperate(str, Enum):
    """Choice 工具支持的数字运算符"""

    EQUAL = "number_equal"
    NOT_EQUAL = "number_not_equal"
    GREATER_THAN = "number_greater_than"
    LESS_THAN = "number_less_than"
    GREATER_THAN_OR_EQUAL = "number_greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "number_less_than_or_equal"


class StringOperate(str, Enum):
    """Choice 工具支持的字符串运算符"""

    EQUAL = "string_equal"
    NOT_EQUAL = "string_not_equal"
    CONTAINS = "string_contains"
    NOT_CONTAINS = "string_not_contains"
    STARTS_WITH = "string_starts_with"
    ENDS_WITH = "string_ends_with"
    LENGTH_EQUAL = "string_length_equal"
    LENGTH_GREATER_THAN = "string_length_greater_than"
    LENGTH_GREATER_THAN_OR_EQUAL = "string_length_greater_than_or_equal"
    LENGTH_LESS_THAN = "string_length_less_than"
    LENGTH_LESS_THAN_OR_EQUAL = "string_length_less_than_or_equal"
    REGEX_MATCH = "string_regex_match"


class ListOperate(str, Enum):
    """Choice 工具支持的列表运算符"""

    EQUAL = "list_equal"
    NOT_EQUAL = "list_not_equal"
    CONTAINS = "list_contains"
    NOT_CONTAINS = "list_not_contains"
    LENGTH_EQUAL = "list_length_equal"
    LENGTH_GREATER_THAN = "list_length_greater_than"
    LENGTH_GREATER_THAN_OR_EQUAL = "list_length_greater_than_or_equal"
    LENGTH_LESS_THAN = "list_length_less_than"
    LENGTH_LESS_THAN_OR_EQUAL = "list_length_less_than_or_equal"


class BoolOperate(str, Enum):
    """Choice 工具支持的布尔运算符"""

    EQUAL = "bool_equal"
    NOT_EQUAL = "bool_not_equal"


class DictOperate(str, Enum):
    """Choice 工具支持的字典运算符"""

    EQUAL = "dict_equal"
    NOT_EQUAL = "dict_not_equal"
    CONTAINS_KEY = "dict_contains_key"
    NOT_CONTAINS_KEY = "dict_not_contains_key"


class Type(str, Enum):
    """Choice 工具支持的类型"""

    STRING = "string"
    NUMBER = "number"
    LIST = "list"
    DICT = "dict"
    BOOL = "bool"
