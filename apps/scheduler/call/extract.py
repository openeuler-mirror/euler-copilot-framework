# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
# JSON字段提取

from typing import List, Dict, Any, Union
from pydantic import Field
import json

from apps.scheduler.call.core import CoreCall, CallParams


class ExtractParams(CallParams):
    """
    校验Extract Call需要的额外参数
    """
    keys: List[str] = Field(description="待提取的JSON字段名称")


class Extract(CoreCall):
    """
    Extract 工具，用于从前一个工具的原始输出中提取指定字段
    """

    name: str = "extract"
    description: str = "从上一步的工具的原始JSON返回结果中，提取特定字段的信息。"
    params_obj: ExtractParams

    def __init__(self, params: Dict[str, Any]):
        self.params_obj = ExtractParams(**params)

    async def call(self, fixed_params: Union[Dict[str, Any], None] = None) -> Dict[str, Any]:
        """
        调用Extract工具
        :param fixed_params: 经用户确认后的参数（目前未使用）
        :return: 提取出的字段
        """

        if len(self.params_obj.keys) == 0:
            raise ValueError("提供的JSON字段Key不能为空！")

        self.params_obj.previous_data = self.params_obj.previous_data["data"]["output"]

        # 根据用户给定的key，找到指定字段
        message_dict = {}
        for key in self.params_obj.keys:
            key_split = key.split(".")
            current_dict = self.params_obj.previous_data
            if isinstance(current_dict, str):
                current_dict = json.loads(current_dict)
            for dict_key in key_split:
                current_dict = current_dict[dict_key]
            message_dict[key_split[-1]] = current_dict

        return {
            "message": json.dumps(message_dict, ensure_ascii=False),
            # 临时将Output字段的类型设置为string，后续应统一改为dict
            "output": json.dumps(message_dict, ensure_ascii=False)
        }
