# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""处理条件分支的工具"""


import logging

from pydantic import BaseModel

from apps.schemas.parameters import (
    Type,
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
    async def get_value_type_from_operate(operate: NumberOperate | StringOperate | ListOperate |
                                          BoolOperate | DictOperate) -> Type:
        """获取右值的类型"""
        if isinstance(operate, NumberOperate):
            return Type.NUMBER
        if operate in [
                StringOperate.EQUAL, StringOperate.NOT_EQUAL, StringOperate.CONTAINS, StringOperate.NOT_CONTAINS,
                StringOperate.STARTS_WITH, StringOperate.ENDS_WITH, StringOperate.REGEX_MATCH]:
            return Type.STRING
        if operate in [StringOperate.LENGTH_EQUAL, StringOperate.LENGTH_GREATER_THAN,
                       StringOperate.LENGTH_GREATER_THAN_OR_EQUAL, StringOperate.LENGTH_LESS_THAN,
                       StringOperate.LENGTH_LESS_THAN_OR_EQUAL]:
            return Type.NUMBER
        if operate in [ListOperate.EQUAL, ListOperate.NOT_EQUAL]:
            return Type.LIST
        if operate in [ListOperate.CONTAINS, ListOperate.NOT_CONTAINS]:
            return Type.STRING
        if operate in [ListOperate.LENGTH_EQUAL, ListOperate.LENGTH_GREATER_THAN,
                       ListOperate.LENGTH_GREATER_THAN_OR_EQUAL, ListOperate.LENGTH_LESS_THAN,
                       ListOperate.LENGTH_LESS_THAN_OR_EQUAL]:
            return Type.NUMBER
        if operate in [BoolOperate.EQUAL, BoolOperate.NOT_EQUAL]:
            return Type.BOOL
        if operate in [DictOperate.EQUAL, DictOperate.NOT_EQUAL]:
            return Type.DICT
        if operate in [DictOperate.CONTAINS_KEY, DictOperate.NOT_CONTAINS_KEY]:
            return Type.STRING
        return None

    @staticmethod
    def check_value_type(value: Value, expected_type: Type) -> bool:
        """检查值的类型是否符合预期"""
        if expected_type == Type.STRING and isinstance(value.value, str):
            return True
        if expected_type == Type.NUMBER and isinstance(value.value, (int, float)):
            return True
        if expected_type == Type.LIST and isinstance(value.value, list):
            return True
        if expected_type == Type.DICT and isinstance(value.value, dict):
            return True
        if expected_type == Type.BOOL and isinstance(value.value, bool):
            return True
        return False

    @staticmethod
    def handler(choices: list[ChoiceBranch]) -> str:
        """处理条件"""

        for block_judgement in choices[::-1]:
            results = []
            if block_judgement.is_default:
                return block_judgement.branch_id
            for condition in block_judgement.conditions:
                result = ConditionHandler._judge_condition(condition)
                if result is not None:
                    results.append(result)
            if not results:
                logger.warning(f"[Choice] 分支 {block_judgement.branch_id} 条件处理失败: 没有有效的条件")
                continue
            if block_judgement.logic == Logic.AND:
                final_result = all(results)
            elif block_judgement.logic == Logic.OR:
                final_result = any(results)

            if final_result:
                return block_judgement.branch_id

        return ""

    @staticmethod
    def _judge_condition(condition: Condition) -> bool:
        """
        判断条件是否成立。

        Args:
            condition (Condition): 'left', 'operate', 'right', 'type'

        Returns:
            bool

        """
        left = condition.left
        operate = condition.operate
        right = condition.right
        value_type = left.type

        result = None
        if value_type == Type.STRING:
            result = ConditionHandler._judge_string_condition(left, operate, right)
        elif value_type == Type.NUMBER:
            result = ConditionHandler._judge_number_condition(left, operate, right)
        elif value_type == Type.BOOL:
            result = ConditionHandler._judge_bool_condition(left, operate, right)
        elif value_type == Type.LIST:
            result = ConditionHandler._judge_list_condition(left, operate, right)
        elif value_type == Type.DICT:
            result = ConditionHandler._judge_dict_condition(left, operate, right)
        else:
            msg = f"不支持的数据类型: {value_type}"
            logger.error(f"[Choice] 条件处理失败: {msg}")
            return None
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
            msg = f"左值必须是字符串类型 ({left_value})"
            logger.warning(msg)
            return None
        right_value = right.value
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
            msg = f"左值必须是数字类型 ({left_value})"
            logger.warning(msg)
            return None
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
            msg = "左值必须是布尔类型"
            logger.warning(msg)
            return None
        right_value = right.value
        if operate == BoolOperate.EQUAL:
            return left_value == right_value
        elif operate == BoolOperate.NOT_EQUAL:
            return left_value != right_value
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
            msg = f"左值必须是列表类型 ({left_value})"
            logger.warning(msg)
            return None
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
            msg = f"左值必须是字典类型 ({left_value})"
            logger.warning(msg)
            return None
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
