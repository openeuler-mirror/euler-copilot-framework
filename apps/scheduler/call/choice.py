"""工具：使用大模型做出选择

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

from pydantic import BaseModel, Field

from apps.entities.plugin import CallError, SysCallVars
from apps.llm.patterns.select import Select
from apps.scheduler.call.core import CoreCall


class _ChoiceBranch(BaseModel):
    """Choice工具的选项"""

    branch: str = Field(description="选项的名称")
    description: str = Field(description="选项的描述")


class _ChoiceParams(BaseModel):
    """Choice工具所需的额外参数"""

    propose: str = Field(description="针对哪一个问题进行答案选择？")
    choices: list[_ChoiceBranch] = Field(description="Choice工具所有可能的选项")


class _ChoiceOutput(BaseModel):
    """Choice工具的输出"""

    message: str = Field(description="Choice工具的输出")
    next_step: str = Field(description="Choice工具的输出")


class Choice(metaclass=CoreCall):
    """Choice工具。用于大模型在多个选项中选择一个，并跳转到对应的Step。"""

    name: str = "choice"
    description: str = "选择工具，用于根据给定的上下文和问题，判断正确/错误，或从选项列表中选择最符合用户要求的一项。"


    async def __call__(self, _slot_data: dict[str, Any]) -> _ChoiceOutput:
        """调用Choice工具。"""
        # 获取必要参数
        params: _ChoiceParams = getattr(self, "_params")
        syscall_vars: SysCallVars = getattr(self, "_syscall_vars")

        previous_data = {}
        if len(syscall_vars.history) > 0:
            previous_data = syscall_vars.history[-1].output_data

        try:
            choice_list = [item.model_dump() for item in params.choices]
            result = await Select().generate(
                question=params.propose,
                background=syscall_vars.background,
                data=previous_data,
                choices=choice_list,
                task_id=syscall_vars.task_id,
            )
        except Exception as e:
            raise CallError(message=f"选择工具调用失败：{e!s}", data={}) from e

        return _ChoiceOutput(
            next_step=result,
            message=f"针对“{params.propose}”，作出的选择为：{result}。",
        )
