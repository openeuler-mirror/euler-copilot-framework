# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""使用大模型或使用程序做出判断"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import Field

from apps.scheduler.call.choice.condition_handler import ConditionHandler
from apps.scheduler.call.choice.schema import (
    ChoiceBranch,
    ChoiceInput,
    ChoiceOutput,
    Logic,
)
from apps.scheduler.call.core import CoreCall
from apps.schemas.enum_var import CallOutputType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)

logger = logging.getLogger(__name__)


class Choice(CoreCall, input_model=ChoiceInput, output_model=ChoiceOutput):
    """Choice工具"""

    to_user: bool = Field(default=False)
    choices: list[ChoiceBranch] = Field(description="分支", default=[])

    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(name="Choice", description="使用大模型或使用程序做出判断")

    async def _prepare_message(self, call_vars: CallVars) -> list[dict[str, Any]]:
        """替换choices中的系统变量"""
        valid_choices = []
        for choice in self.choices:
            if choice.logic not in [Logic.AND, Logic.OR]:
                logger.warning("分支 %s 的逻辑运算符 %s 无效，已跳过",choice.branch_id, choice.logic)
                continue
            valid_conditions = []
            for condition in choice.conditions:
                if condition.left.step_id:
                    condition.left.value = self._extract_history_variables(
                        condition.left.step_id, call_vars.history,
                    )
                    valid_conditions.append(condition)
                else:
                    logger.warning("条件 %s 的左侧变量 %s 无效，已跳过", condition.condition_id, condition.left)
                    continue
            choice.conditions = valid_conditions
            valid_choices.append(choice.dict())
        return valid_choices

    async def _init(self, call_vars: CallVars) -> ChoiceInput:
        """初始化Choice工具"""
        return ChoiceInput(
            choices=await self._prepare_message(call_vars),
        )

    async def _exec(
        self, input_data: dict[str, Any]
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """执行Choice工具"""
        # 解析输入数据
        data = ChoiceInput(**input_data)
        ret: CallOutputChunk = CallOutputChunk(
            type=CallOutputType.DATA,
            content=None,
        )
        condition_handler = ConditionHandler()
        try:
            ret.content = condition_handler.handler(data.choices)
            yield ret
        except Exception as e:
            raise CallError(message=f"选择工具调用失败：{e!s}", data={}) from e
