# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""处理条件分支的工具"""

import logging

from pydantic import BaseModel

from apps.scheduler.call.choice.schema import ChoiceBranch, ChoiceOutput, Condition, Logic, Operator, Type, Value

logger = logging.getLogger(__name__)


class ConditionHandler(BaseModel):
    """条件分支处理器"""

    def handler(self, choices: list[ChoiceBranch]) -> ChoiceOutput:
        """处理条件"""
        default_branch = [c for c in choices if c.is_default]

        for block_judgement in choices:
            results = []
            if block_judgement.is_default:
                continue
            for condition in block_judgement.conditions:
                result = self._judge_condition(condition)
                results.append(result)
            if block_judgement.logic == Logic.AND:
                final_result = all(results)
            elif block_judgement.logic == Logic.OR:
                final_result = any(results)

            if final_result:
                return {
                    "branch_id": block_judgement.branch_id,
                    "message": f"选择分支：{block_judgement.branch_id}",
                }

        # 如果没有匹配的分支，选择默认分支
        if default_branch:
            return {
                "branch_id": default_branch[0].branch_id,
                "message": f"选择默认分支：{default_branch[0].branch_id}",
            }
        return {
            "branch_id": "",
            "message": "没有匹配的分支，且没有默认分支",
        }

    def _judge_condition(self, condition: Condition) -> bool:
        """
        判断条件是否成立。

        Args:
            condition (Condition): 'left', 'operator', 'right', 'type'

        Returns:
            bool

        """
        left = condition.left
        operator = condition.operator
        right = condition.right
        value_type = condition.type

        result = None
        if value_type == Type.STRING:
            result = self._judge_string_condition(left, operator, right)
        elif value_type == Type.INT:
            result = self._judge_int_condition(left, operator, right)
        elif value_type == Type.BOOL:
            result = self._judge_bool_condition(left, operator, right)
        else:
            logger.error("不支持的数据类型: %s", value_type)
            msg = f"不支持的数据类型: {value_type}"
            raise ValueError(msg)
        return result

    def _judge_string_condition(self, left: Value, operator: Operator, right: Value) -> bool:
        """
        判断字符串类型的条件。

        Args:
            left (Value): 左值，包含 'value' 键。
            operator (Operator): 操作符
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
        if operator == Operator.EQUAL:
            result = left_value == right_value
        elif operator == Operator.NEQUAL:
            result = left_value != right_value
        elif operator == Operator.GREAT:
            result = len(left_value) > len(right_value)
        elif operator == Operator.GREAT_EQUALS:
            result = len(left_value) >= len(right_value)
        elif operator == Operator.LESS:
            result = len(left_value) < len(right_value)
        elif operator == Operator.LESS_EQUALS:
            result = len(left_value) <= len(right_value)
        elif operator == Operator.GREATER:
            result = left_value > right_value
        elif operator == Operator.GREATER_EQUALS:
            result = left_value >= right_value
        elif operator == Operator.SMALLER:
            result = left_value < right_value
        elif operator == Operator.SMALLER_EQUALS:
            result = left_value <= right_value
        elif operator == Operator.CONTAINS:
            result = right_value in left_value
        elif operator == Operator.NOT_CONTAINS:
            result = right_value not in left_value
        return result

    def _judge_int_condition(self, left: Value, operator: Operator, right: Value) -> bool:  # noqa: PLR0911
        """
        判断整数类型的条件。

        Args:
            left (Value): 左值，包含 'value' 键。
            operator (Operator): 操作符
            right (Value): 右值，包含 'value' 键。

        Returns:
            bool

        """
        left_value = left.value
        if not isinstance(left_value, int):
            logger.error("左值不是整数类型: %s", left_value)
            msg = "左值必须是整数类型"
            raise TypeError(msg)
        right_value = right.value
        if operator == Operator.EQUAL:
            return left_value == right_value
        if operator == Operator.NEQUAL:
            return left_value != right_value
        if operator == Operator.GREAT:
            return left_value > right_value
        if operator == Operator.GREAT_EQUALS:
            return left_value >= right_value
        if operator == Operator.LESS:
            return left_value < right_value
        if operator == Operator.LESS_EQUALS:
            return left_value <= right_value
        return False

    def _judge_bool_condition(self, left: Value, operator: Operator, right: Value) -> bool:
        """
        判断布尔类型的条件。

        Args:
            left (Value): 左值，包含 'value' 键。
            operator (Operator): 操作符
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
        if operator == Operator.EQUAL:
            return left_value == right_value
        if operator == Operator.NEQUAL:
            return left_value != right_value
        if operator == Operator.IS_EMPTY:
            return left_value == ""
        if operator == Operator.NOT_EMPTY:
            return left_value != ""
        return False
