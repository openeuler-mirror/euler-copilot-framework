"""基础大模型范式抽象类

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from abc import ABC, abstractmethod
from textwrap import dedent
from typing import Any, ClassVar, Optional


class CorePattern(ABC):
    """基础大模型范式抽象类"""

    system_prompt: str = ""
    """系统提示词"""
    user_prompt: str = ""
    """用户提示词"""
    slot_schema: ClassVar[dict[str, Any]] = {}
    """输出格式的JSON Schema"""

    def __init__(self, system_prompt: Optional[str] = None, user_prompt: Optional[str] = None) -> None:
        """检查是否已经自定义了Prompt；有的话就用自定义的；同时对Prompt进行空格清除

        :param system_prompt: 系统提示词，f-string格式
        :param user_prompt: 用户提示词，f-string格式
        """
        if system_prompt is not None:
            self.system_prompt = system_prompt

        if user_prompt is not None:
            self.user_prompt = user_prompt

        if not self.system_prompt or not self.user_prompt:
            err = "必须设置系统提示词和用户提示词！"
            raise ValueError(err)

        self.system_prompt = dedent(self.system_prompt).strip("\n")
        self.user_prompt = dedent(self.user_prompt).strip("\n")

    @abstractmethod
    async def generate(self, task_id: str, **kwargs):  # noqa: ANN003, ANN201
        """调用大模型，生成结果"""
        raise NotImplementedError
