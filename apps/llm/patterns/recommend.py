"""使用大模型进行推荐问题生成

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, ClassVar, Optional

from apps.llm.patterns.core import CorePattern
from apps.llm.patterns.json_gen import Json
from apps.llm.reasoning import ReasoningLLM
from apps.llm.snippet import convert_context_to_prompt, history_questions_to_prompt


class Recommend(CorePattern):
    """使用大模型进行推荐问题生成"""

    system_prompt: str = ""
    """系统提示词"""

    user_prompt: str = r"""
        <instructions>
            <instruction>
                根据提供的对话和附加信息（用户倾向、历史问题列表等），生成三个预测问题。
                历史提问列表展示的是用户发生在历史对话之前的提问，仅为背景参考作用。
                对话将在<conversation>标签中给出，用户倾向将在<domain>标签中给出，历史问题列表将在<history_list>标签中给出。

                生成预测问题时的要求：
                    1. 以用户口吻生成预测问题，数量必须为3个，必须为疑问句或祈使句，必须少于30字。
                    2. 预测问题必须精简，不得发生重复，不得在问题中掺杂非必要信息，不得输出除问题以外的文字。
                    3. 输出必须按照如下格式：

                    ```json
                    {{
                        "predicted_questions": [
                            "预测问题1",
                            "预测问题2",
                            "预测问题3"
                        ]
                    }}
                    ```
            </instruction>

            <example>
                <conversation>
                    <user>杭州有哪些著名景点？</user>
                    <assistant>杭州西湖是中国浙江省杭州市的一个著名景点，以其美丽的自然风光和丰富的文化遗产而闻名。西湖周围有许多著名的景点，包括著名的苏堤、白堤、断桥、三潭印月等。西湖以其清澈的湖水和周围的山脉而著名，是中国最著名的湖泊之一。</assistant>
                </conversation>
                <history_list>
                    <question>简单介绍一下杭州</question>
                    <question>杭州有哪些著名景点？</question>
                </history_list>
                <domain>["杭州", "旅游"]</domain>

                现在，进行问题生成：

                {{
                    "predicted_questions": [
                        "杭州西湖景区的门票价格是多少？",
                        "杭州有哪些著名景点？",
                        "杭州的天气怎么样？"
                    ]
                }}
            </example>
        </instructions>


        <conversation>
            {conversation}
        </conversation>

        <history_list>
            {history_questions}
        </history_list>

        <domain>{user_preference}</domain>

        现在，进行问题生成：
    """
    """用户提示词"""

    slot_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "predicted_questions": {
                "type": "array",
                "description": "推荐的问题列表",
                "items": {
                    "type": "string",
                },
            },
        },
        "required": ["predicted_questions"],
    }
    """最终输出的JSON Schema"""


    def __init__(self, system_prompt: Optional[str] = None, user_prompt: Optional[str] = None) -> None:
        """初始化推荐问题生成Prompt"""
        super().__init__(system_prompt, user_prompt)


    async def generate(self, task_id: str, **kwargs) -> list[str]:  # noqa: ANN003
        """生成推荐问题"""
        if "user_preference" not in kwargs or not kwargs["user_preference"]:
            user_preference = "[Empty]"
        else:
            user_preference = kwargs["user_preference"]

        if "history_questions" not in kwargs or not kwargs["history_questions"]:
            history_questions = "[Empty]"
        else:
            history_questions = history_questions_to_prompt(kwargs["history_questions"])

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(
                conversation=convert_context_to_prompt(kwargs["conversation"]),
                history_questions=history_questions,
                user_preference=user_preference,
            )},
        ]

        result = ""
        async for chunk in ReasoningLLM().call(task_id, messages, streaming=False, temperature=0.7):
            result += chunk
        messages += [{"role": "assistant", "content": result}]

        question_dict = await Json().generate("", conversation=messages, spec=self.slot_schema)

        if not question_dict or "predicted_questions" not in question_dict or not question_dict["predicted_questions"]:
            return []

        return question_dict["predicted_questions"]
