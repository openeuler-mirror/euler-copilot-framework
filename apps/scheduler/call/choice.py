"""工具：使用大模型做出选择

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from apps.entities.plugin import CallError, CallResult, SysCallVars
from apps.llm.patterns.select import Select
from apps.scheduler.call.core import CoreCall


class _ChoiceParams(BaseModel):
    """Choice工具所需的额外参数"""

    propose: str = Field(description="针对哪一个问题进行答案选择？")
    choices: list[dict[str, Any]] = Field(description="Choice工具所有可能的选项")


class Choice(CoreCall):
    """Choice工具。用于大模型在多个选项中选择一个，并跳转到对应的Step。"""

    def __init__(self, syscall_vars: SysCallVars, **kwargs) -> None:  # noqa: ANN003
        """初始化Choice工具，解析参数。

        :param params: Choice工具所需的参数
        """
        self._core_params = syscall_vars
        self._params = _ChoiceParams.model_validate(kwargs)
        # 初始化Slot Schema
        self.slot_schema = {}


    name: str = "choice"
    description: str = "选择工具，用于根据给定的上下文和问题，判断正确/错误，或从选项列表中选择最符合用户要求的一项。"
    params_schema: ClassVar[dict[str, Any]] = _ChoiceParams.model_json_schema()


    async def call(self, _slot_data: dict[str, Any]) -> CallResult:
        """调用Choice工具。

        :param _slot_data: 经用户修正过的参数（暂未使用）
        :return: Choice工具的输出信息。包含下一个Step的名称、自然语言解释等。
        """
        previous_data = {}
        if len(self._core_params.history) > 0:
            previous_data = CallResult(**self._core_params.history[-1].output_data).output

        try:
            result = await Select().generate(
                question=self._params.propose,
                background=self._core_params.background,
                data=previous_data,
                choices=self._params.choices,
                task_id=self._core_params.task_id,
            )
        except Exception as e:
            raise CallError(message=f"选择工具调用失败：{e!s}", data={}) from e

        return CallResult(
            output={},
            output_schema={},
            extra={
                "next_step": result,
            },
            message=f"针对“{self._params.propose}”，作出的选择为：{result}。",
        )
