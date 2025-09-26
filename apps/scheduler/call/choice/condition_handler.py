# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""处理条件分支的工具"""


import logging

from pydantic import BaseModel

from apps.schemas.parameters import (
    ValueType,
    NumberOperate,
    StringOperate,
    ListOperate,
    BoolOperate,
    DictOperate,
)

from apps.scheduler.call.choice.schema import (
    ChoiceBranch,
    Condition,
    Logic,
    Value
)

logger = logging.getLogger(__name__)


class ConditionHandler(BaseModel):
    """条件分支处理器"""
    @staticmethod
    def get_value_type_from_operate(operate: NumberOperate | StringOperate | ListOperate |
                                    BoolOperate | DictOperate) -> ValueType:
        """根据逻辑运算符获取值的类型"""
        if isinstance(operate, NumberOperate):
            return ValueType.NUMBER
        if operate in [
                StringOperate.EQUAL, StringOperate.NOT_EQUAL, StringOperate.CONTAINS, StringOperate.NOT_CONTAINS,
                StringOperate.STARTS_WITH, StringOperate.ENDS_WITH, StringOperate.REGEX_MATCH]:
            return ValueType.STRING
        if operate in [StringOperate.LENGTH_EQUAL, StringOperate.LENGTH_GREATER_THAN,
                       StringOperate.LENGTH_GREATER_THAN_OR_EQUAL, StringOperate.LENGTH_LESS_THAN,
                       StringOperate.LENGTH_LESS_THAN_OR_EQUAL]:
            return ValueType.NUMBER
        if operate in [ListOperate.EQUAL, ListOperate.NOT_EQUAL]:
            return ValueType.LIST
        if operate in [ListOperate.CONTAINS, ListOperate.NOT_CONTAINS]:
            return ValueType.STRING
        if operate in [ListOperate.LENGTH_EQUAL, ListOperate.LENGTH_GREATER_THAN,
                       ListOperate.LENGTH_GREATER_THAN_OR_EQUAL, ListOperate.LENGTH_LESS_THAN,
                       ListOperate.LENGTH_LESS_THAN_OR_EQUAL]:
            return ValueType.NUMBER
        if operate in [BoolOperate.EQUAL, BoolOperate.NOT_EQUAL]:
            return ValueType.BOOL
        if operate in [DictOperate.EQUAL, DictOperate.NOT_EQUAL]:
            return ValueType.DICT
        if operate in [DictOperate.CONTAINS_KEY, DictOperate.NOT_CONTAINS_KEY]:
            return ValueType.STRING
        return None

    @staticmethod
    def check_value_type(value: Value) -> bool:
        """检查值的类型是否符合预期"""
        if value.type == ValueType.STRING and isinstance(value.value, str):
            return True
        if value.type == ValueType.NUMBER and isinstance(value.value, (int, float)):
            return True
        if value.type == ValueType.LIST and isinstance(value.value, list):
            return True
        if value.type == ValueType.DICT and isinstance(value.value, dict):
            return True
        if value.type == ValueType.BOOL and isinstance(value.value, bool):
            return True
        # 添加对REFERENCE类型的处理 - 如果是REFERENCE类型但没有被解析，说明解析失败
        # 在这种情况下，我们将其视为字符串类型进行基本的兼容性检查
        if value.type == ValueType.REFERENCE and isinstance(value.value, str):
            return True
        return False

    @staticmethod
    def handler(choices: list[ChoiceBranch]) -> str:
        """处理条件"""
        default_branch = [c for c in choices if c.is_default]

        # 先处理所有非默认分支
        for block_judgement in choices:
            results = []
            # 跳过默认分支，先处理有条件的分支
            if block_judgement.is_default:
                continue
                
            for condition in block_judgement.conditions:
                result = ConditionHandler._judge_condition(condition)
                results.append(result)
                
            if block_judgement.logic == Logic.AND:
                final_result = all(results)
            elif block_judgement.logic == Logic.OR:
                final_result = any(results)
            else:
                # 如果没有逻辑运算符但有条件，默认使用AND逻辑
                final_result = all(results) if results else False

            if final_result:
                return block_judgement.branch_id
    
        # 如果所有非默认分支都不满足条件，返回默认分支
        if default_branch:
            return default_branch[0].branch_id
            
        return ""

    @staticmethod
    def _judge_condition(condition: Condition) -> bool:
        """
        判断条件是否成立。

        Args:
            condition (Condition): 'left', 'operator', 'right'

        Returns:
            bool

        """
        left = condition.left
        operator = condition.operator
        right = condition.right
        
        # 根据操作符动态推断值类型
        try:
            value_type = ConditionHandler.get_value_type_from_operate(operator)
        except Exception as e:
            logger.error("无法推断操作符 %s 的值类型: %s", operator, e)
            msg = f"无法推断操作符 {operator} 的值类型: {e}"
            raise ValueError(msg)

        result = None
        if value_type == ValueType.STRING:
            result = ConditionHandler._judge_string_condition(left, operator, right)
        elif value_type == ValueType.NUMBER:
            result = ConditionHandler._judge_number_condition(left, operator, right)
        elif value_type == ValueType.BOOL:
            result = ConditionHandler._judge_bool_condition(left, operator, right)
        elif value_type == ValueType.LIST:
            result = ConditionHandler._judge_list_condition(left, operator, right)
        elif value_type == ValueType.DICT:
            result = ConditionHandler._judge_dict_condition(left, operator, right)
        else:
            msg = f"不支持的值类型: {value_type}"
            raise ValueError(msg)

        return result

    @staticmethod
    def _judge_string_condition(left: Value, operate: StringOperate, right: Value) -> bool:
        """
        判断字符串类型的条件。

        Args:
            left (Value): 左值，包含 'value' 键。
            operate (Operate): 操作符
            right (Value): 右值，包含 'value' 键。

        Returns:
            bool

        """
        left_value = left.value
        if not isinstance(left_value, str):
            logger.error("左值不是字符串类型: %s", left_value)
            msg = "左值必须是字符串类型"
            raise TypeError(msg)
        right_value = right.value
        result = False
        if operate == StringOperate.EQUAL:
            return left_value == right_value
        elif operate == StringOperate.NOT_EQUAL:
            return left_value != right_value
        elif operate == StringOperate.CONTAINS:
            return right_value in left_value
        elif operate == StringOperate.NOT_CONTAINS:
            return right_value not in left_value
        elif operate == StringOperate.STARTS_WITH:
            return left_value.startswith(right_value)
        elif operate == StringOperate.ENDS_WITH:
            return left_value.endswith(right_value)
        elif operate == StringOperate.REGEX_MATCH:
            import re
            return bool(re.match(right_value, left_value))
        elif operate == StringOperate.LENGTH_EQUAL:
            return len(left_value) == right_value
        elif operate == StringOperate.LENGTH_GREATER_THAN:
            return len(left_value) > right_value
        elif operate == StringOperate.LENGTH_GREATER_THAN_OR_EQUAL:
            return len(left_value) >= right_value
        elif operate == StringOperate.LENGTH_LESS_THAN:
            return len(left_value) < right_value
        elif operate == StringOperate.LENGTH_LESS_THAN_OR_EQUAL:
            return len(left_value) <= right_value
        return False

    @staticmethod
    def _judge_number_condition(left: Value, operate: NumberOperate, right: Value) -> bool:  # noqa: PLR0911
        """
        判断数字类型的条件。

        Args:
            left (Value): 左值，包含 'value' 键。
            operate (Operate): 操作符
            right (Value): 右值，包含 'value' 键。

        Returns:
            bool

        """
        left_value = left.value
        if not isinstance(left_value, (int, float)):
            logger.error("左值不是数字类型: %s", left_value)
            msg = "左值必须是数字类型"
            raise TypeError(msg)
        right_value = right.value
        if operate == NumberOperate.EQUAL:
            return left_value == right_value
        elif operate == NumberOperate.NOT_EQUAL:
            return left_value != right_value
        elif operate == NumberOperate.GREATER_THAN:
            return left_value > right_value
        elif operate == NumberOperate.LESS_THAN:  # noqa: PLR2004
            return left_value < right_value
        elif operate == NumberOperate.GREATER_THAN_OR_EQUAL:
            return left_value >= right_value
        elif operate == NumberOperate.LESS_THAN_OR_EQUAL:
            return left_value <= right_value
        return False

    @staticmethod
    def _judge_bool_condition(left: Value, operate: BoolOperate, right: Value) -> bool:
        """
        判断布尔类型的条件。

        Args:
            left (Value): 左值，包含 'value' 键。
            operate (Operate): 操作符
            right (Value): 右值，包含 'value' 键。

        Returns:
            bool

        """
        left_value = left.value
        if not isinstance(left_value, bool):
            logger.error("左值不是布尔类型: %s", left_value)
            msg = "左值必须是布尔类型"
            raise TypeError(msg)
        right_value = right.value
        if operate == BoolOperate.EQUAL:
            return left_value == right_value
        elif operate == BoolOperate.NOT_EQUAL:
            return left_value != right_value
        elif operate == BoolOperate.IS_EMPTY:
            return not left_value
        elif operate == BoolOperate.NOT_EMPTY:
            return left_value
        return False

    @staticmethod
    def _judge_list_condition(left: Value, operate: ListOperate, right: Value):
        """
        判断列表类型的条件。

        Args:
            left (Value): 左值，包含 'value' 键。
            operate (Operate): 操作符
            right (Value): 右值，包含 'value' 键。

        Returns:
            bool

        """
        left_value = left.value
        if not isinstance(left_value, list):
            logger.error("左值不是列表类型: %s", left_value)
            msg = "左值必须是列表类型"
            raise TypeError(msg)
        right_value = right.value
        if operate == ListOperate.EQUAL:
            return left_value == right_value
        elif operate == ListOperate.NOT_EQUAL:
            return left_value != right_value
        elif operate == ListOperate.CONTAINS:
            return right_value in left_value
        elif operate == ListOperate.NOT_CONTAINS:
            return right_value not in left_value
        elif operate == ListOperate.LENGTH_EQUAL:
            return len(left_value) == right_value
        elif operate == ListOperate.LENGTH_GREATER_THAN:
            return len(left_value) > right_value
        elif operate == ListOperate.LENGTH_GREATER_THAN_OR_EQUAL:
            return len(left_value) >= right_value
        elif operate == ListOperate.LENGTH_LESS_THAN:
            return len(left_value) < right_value
        elif operate == ListOperate.LENGTH_LESS_THAN_OR_EQUAL:
            return len(left_value) <= right_value
        return False

    @staticmethod
    def _judge_dict_condition(left: Value, operate: DictOperate, right: Value):
        """
        判断字典类型的条件。

        Args:
            left (Value): 左值，包含 'value' 键。
            operate (Operate): 操作符
            right (Value): 右值，包含 'value' 键。

        Returns:
            bool

        """
        left_value = left.value
        if not isinstance(left_value, dict):
            logger.error("左值不是字典类型: %s", left_value)
            msg = "左值必须是字典类型"
            raise TypeError(msg)
        right_value = right.value
        if operate == DictOperate.EQUAL:
            return left_value == right_value
        elif operate == DictOperate.NOT_EQUAL:
            return left_value != right_value
        elif operate == DictOperate.CONTAINS_KEY:
            return right_value in left_value
        elif operate == DictOperate.NOT_CONTAINS_KEY:
            return right_value not in left_value
        return False
