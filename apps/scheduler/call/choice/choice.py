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

    def _raise_value_error(self, msg: str) -> None:
        """统一处理 ValueError 异常抛出"""
        logger.warning(msg)
        raise ValueError(msg)

    async def _prepare_message(self, call_vars: CallVars) -> list[dict[str, Any]]:
        """替换choices中的系统变量"""
        valid_choices = []

        for choice in self.choices:
            try:
                # 验证逻辑运算符
                if choice.logic not in [Logic.AND, Logic.OR]:
                    msg = f"无效的逻辑运算符: {choice.logic}"
                    self._raise_value_error(msg)

                valid_conditions = []
                for condition in choice.conditions:
                    # 处理左值
                    if condition.left.step_id:
                        condition.left.value = self._extract_history_variables(condition.left.step_id, call_vars.history)
                        # 检查历史变量是否成功提取
                    if condition.left.value is None:
                        msg = f"步骤 {condition.left.step_id} 的历史变量不存在"
                        self._raise_value_error(msg)
                    else:
                        msg = "左侧变量缺少step_id"
                        self._raise_value_error(msg)

                valid_conditions.append(condition)

                # 如果所有条件都无效，抛出异常
                if not valid_conditions:
                    msg = "分支没有有效条件"
                    self._raise_value_error(msg)

                # 更新有效条件
                choice.conditions = valid_conditions
                valid_choices.append(choice.dict())

            except ValueError as e:
                logger.warning("分支 %s 处理失败: %s，已跳过", choice.branch_id, str(e))
                continue

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
