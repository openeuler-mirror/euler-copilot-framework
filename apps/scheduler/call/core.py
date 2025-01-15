"""Core Call类，定义了所有Call的抽象类和基础参数。

所有Call类必须继承此类，并实现所有方法。
Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

from pydantic import BaseModel

from apps.entities.plugin import CallResult, SysCallVars


class AdditionalParams(BaseModel):
    """Call的额外参数"""



class CoreCall:
    """Call抽象类。所有Call必须继承此类，并实现所有方法。"""

    name: str = ""
    description: str = ""
    params: type[BaseModel] = AdditionalParams

    @property
    def params_schema(self) -> dict[str, Any]:
        """返回params的schema"""
        return self.params.model_json_schema()

    async def init(self, syscall_vars: SysCallVars, **kwargs) -> None:  # noqa: ANN003
        """初始化Call，赋值参数

        :param syscall_vars: Call所需的固定参数。此处的参数为系统提供。
        :param kwargs: Call所需的额外参数。此处的参数为Flow开发者填充。
        """
        # 使用此种方式进行params校验
        self._syscall_vars = syscall_vars
        self._params = self.params.model_validate(kwargs)
        # 在此初始化Slot Schema
        self.slot_schema: dict[str, Any] = {}

    async def load(self) -> None:
        """如果Call需要载入文件，则在这里定义逻辑"""
        pass  # noqa: PIE790

    async def call(self, slot_data: dict[str, Any]) -> CallResult:
        """运行Call。

        :param slot_data: Call的参数槽。此处的参数槽为用户通过大模型交互式填充。
        :return: CallResult类型的数据。返回值中"output"为工具的原始返回信息（有格式字符串）；"message"为工具经LLM处理后的返回信息（字符串）。也可以带有其他字段，其他字段将起到额外的说明和信息传递作用。
        """
        raise NotImplementedError
