"""LLM Pattern: 从问答中提取领域信息

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, ClassVar, Optional

from apps.llm.patterns.core import CorePattern
from apps.llm.patterns.json import Json
from apps.llm.reasoning import ReasoningLLM


class Domain(CorePattern):
    """从问答中提取领域信息"""

    user_prompt: str = r"""
        <instructions>
          <instruction>
            根据对话上文，提取推荐系统所需的关键词标签，要求：
            1. 实体名词、技术术语、时间范围、地点、产品等关键信息均可作为关键词标签
            2. 至少一个关键词与对话的话题有关
            3. 标签需精简，不得重复，不得超过10个字
            4. 使用JSON格式输出，不要包含XML标签，不要包含任何解释说明
          </instruction>

          <example>
            <conversation>
              <user>北京天气如何？</user>
              <assistant>北京今天晴。</assistant>
            </conversation>

            <output>
              {
                "keywords": ["北京", "天气"]
              }
            </output>
          </example>
        </instructions>

        <conversation>
          {conversation}
        </conversation>
        <output>
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
            {"role": "system", "content": ""},
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
