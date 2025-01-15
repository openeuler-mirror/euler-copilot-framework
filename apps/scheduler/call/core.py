"""Core Call类，定义了所有Call的抽象类和基础参数。

所有Call类必须继承此类，并实现所有方法。
Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from apps.entities.plugin import CallResult, SysCallVars


class AdditionalParams(BaseModel):
    """Call的额外参数"""



class CoreCall(ABC):
    """Call抽象类。所有Call必须继承此类，并实现所有方法。"""

    name: str = ""
    description: str = ""
    params_schema: ClassVar[dict[str, Any]] = {}


    @abstractmethod
    def __init__(self, syscall_vars: SysCallVars, **kwargs) -> None:  # noqa: ANN003
        """初始化Call，并对参数进行解析。

        :param syscall_vars: Call所需的固定参数。此处的参数为系统提供。
        :param kwargs: Call所需的额外参数。此处的参数为Flow开发者填充。
        """
        # 使用此种方式进行params校验
        self._syscall_vars = syscall_vars
        self._params = AdditionalParams.model_validate(kwargs)
        # 在此初始化Slot Schema
        self.slot_schema: dict[str, Any] = {}


    @abstractmethod
    async def call(self, slot_data: dict[str, Any]) -> CallResult:
        """运行Call。

        :param slot_data: Call的参数槽。此处的参数槽为用户通过大模型交互式填充。
        :return: Dict类型的数据。返回值中"output"为工具的原始返回信息（有格式字符串）；"message"为工具经LLM处理后的返回信息（字符串）。也可以带有其他字段，其他字段将起到额外的说明和信息传递作用。
        """
        raise NotImplementedError
