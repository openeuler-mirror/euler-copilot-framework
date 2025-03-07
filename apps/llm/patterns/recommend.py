"""使用大模型进行推荐问题生成

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, ClassVar, Optional

from apps.llm.patterns.core import CorePattern
from apps.llm.patterns.json_gen import Json
from apps.llm.reasoning import ReasoningLLM


class Recommend(CorePattern):
    """使用大模型进行推荐问题生成"""

    system_prompt: str = ""
    """系统提示词"""

    user_prompt: str = r"""
        ## 目标：
        根据上面的历史对话，结合给出的工具描述和用户倾向，生成三个预测问题。

        ## 要求：
        信息说明：
        - [Empty]的含义是“空信息”，如“工具描述: [Empty]”表示当前未使用工具。请忽略信息为空的项，正常进行问题预测。
        - 历史提问信息是用户发生在历史对话之前的提问，仅为背景参考作用。

        生成时需要遵循的要求：
        1. 从用户角度生成预测问题，数量必须为3个，必须为疑问句或祈使句，必须少于30字。
        2. 预测问题应优先贴合工具描述，除非工具描述为空。
        3. 预测问题必须精简，不得在问题中掺杂非必要信息，不得输出除问题以外的文字。
        4. 请以如下格式输出：

        ```json
        {{
            "predicted_questions": [
                "预测问题1",
                "预测问题2",
                "预测问题3"
            ]
        }}
        ```

        ## 样例：
        工具描述：调用API，查询天气数据

        用户历史提问：
        - 简单介绍杭州
        - 杭州有哪些著名景点

        用户倾向：
        ['旅游', '美食']

        生成的预测问题：
        ```json
        {{
            "predicted_questions": [
                "杭州西湖景区的门票价格是多少？",
                "杭州有哪些著名景点？",
                "杭州的天气怎么样？"
            ]
        }}
        ```

        ## 现在，进行问题生成：
        工具描述：{action_description}

        用户历史提问：
        {history_questions}

        用户倾向：
        {user_preference}

        生成的预测问题：
        ```json
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
        if "action_description" not in kwargs or not kwargs["action_description"]:
            action_description = "[Empty]"
        else:
            action_description = kwargs["action_description"]

        if "user_preference" not in kwargs or not kwargs["user_preference"]:
            user_preference = "[Empty]"
        else:
            user_preference = kwargs["user_preference"]

        if "history_questions" not in kwargs or not kwargs["history_questions"]:
            history_questions = "[Empty]"
        else:
            history_questions = kwargs["history_questions"]

        user_input = self.user_prompt.format(
            action_description=action_description,
            history_questions=history_questions,
            user_preference=user_preference,
        )

        messages = kwargs["recent_question"] + [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]

        result = ""
        async for chunk in ReasoningLLM().call(task_id, messages, streaming=False, temperature=0.7):
            result += chunk
        messages += [{"role": "assistant", "content": result}]

        question_dict = await Json().generate("", conversation=messages, spec=self.slot_schema)

        if not question_dict or "predicted_questions" not in question_dict or not question_dict["predicted_questions"]:
            return []

        return question_dict["predicted_questions"]
