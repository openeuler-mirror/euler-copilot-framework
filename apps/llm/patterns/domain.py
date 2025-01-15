"""LLM Pattern: 从问答中提取领域信息

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, ClassVar, Optional

from apps.llm.patterns.core import CorePattern
from apps.llm.patterns.json import Json
from apps.llm.reasoning import ReasoningLLM


class Domain(CorePattern):
    """从问答中提取领域信息"""

    system_prompt: str = r"""
        Your task is: Extract feature tags and categories from given conversations.
        Tags and categories will be used in a recommendation system to offer search keywords to users.

        Conversations will be given between "<conversation>" and "</conversation>" tags.

        EXAMPLE 1

        CONVERSATION:
        <conversation>
        User: What is the weather in Beijing?
        Assistant: It is sunny in Beijing.
        </conversation>

        OUTPUT:
        Beijing, weather
        END OF EXAMPLE 1


        EXAMPLE 2

        CONVERSATION:
        <conversation>
        User: Check CVEs on host 1 from 2024-01-01 to 2024-01-07.
        Assistant: There are 3 CVEs on host 1 from 2024-01-01 to 2024-01-07, including CVE-2024-0001, CVE-2024-0002, and CVE-2024-0003.
        </conversation>

        OUTPUT:
        CVE, host 1, Cybersecurity

        END OF EXAMPLE 2
    """
    """系统提示词"""

    user_prompt: str = r"""
        CONVERSATION:
        <conversation>
        {conversation}
        </conversation>

        OUTPUT:
    """
    """用户提示词"""

    slot_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "array",
                "description": "feature tags and categories, can be empty",
            },
        },
        "required": ["keywords"],
    }
    """最终输出的JSON Schema"""

    def __init__(self, system_prompt: Optional[str] = None, user_prompt: Optional[str] = None) -> None:
        """初始化Reflect模式"""
        super().__init__(system_prompt, user_prompt)


    async def generate(self, task_id: str, **kwargs) -> list[str]:  # noqa: ANN003
        """从问答中提取领域信息"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(conversation=kwargs["conversation"])},
        ]

        result = ""
        async for chunk in ReasoningLLM().call(task_id, messages, streaming=False):
            result += chunk

        messages += [
            {"role": "assistant", "content": result},
        ]

        output = await Json().generate(task_id, conversation=messages, spec=self.slot_schema)
        return output["keywords"]
