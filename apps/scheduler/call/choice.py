# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from typing import Dict, Any, List, Union
from pydantic import Field

from apps.scheduler.call.core import CoreCall, CallParams
from apps.scheduler.utils.consistency import Consistency


class ChoiceParams(CallParams):
    """
    Choice工具所需的额外参数
    """
    instruction: str = Field(description="针对哪一个问题进行答案选择？")
    choices: List[Dict[str, Any]] = Field(description="Choice工具所有可能的选项")


class Choice(CoreCall):
    """
    Choice工具。用于大模型在多个选项中选择一个，并跳转到对应的Step。
    """
    name = "choice"
    description = "选择工具，用于根据给定的上下文和问题，判断正确/错误，或从选项列表中选择最符合用户要求的一项。"
    params_obj: ChoiceParams

    def __init__(self, params: Dict[str, Any]):
        """
        初始化Choice工具，解析参数。
        :param params: Choice工具所需的参数
        """
        self.params_obj = ChoiceParams(**params)

    async def call(self, fixed_params: Union[Dict[str, Any], None] = None) -> Dict[str, Any]:
        """
        调用Choice工具。
        :param fixed_params: 经用户修正过的参数（暂未使用）
        :return: Choice工具的输出信息。包含下一个Step的名称、自然语言解释等。
        """
        result = await Consistency().consistency(
            instruction=self.params_obj.instruction,
            background=self.params_obj.background,
            data=self.params_obj.previous_data,
            choices=self.params_obj.choices
        )
        return {
            "output": result,
            "next_step": result,
            "message": f"针对“{self.params_obj.instruction}”，作出的选择为：{result}。"
        }
