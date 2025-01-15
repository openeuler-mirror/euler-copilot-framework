# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from typing import Optional

from apps.llm.patterns.core import CorePattern


class RenderFormat(CorePattern):
    _system_prompt = ""
    _user_prompt = ""

    def __init__(self, system_prompt: Optional[str] = None, user_prompt: Optional[str] = None) -> None:
        super().__init__(system_prompt, user_prompt)

    async def generate(self, task_id: str, **kwargs) -> str:
        pass
