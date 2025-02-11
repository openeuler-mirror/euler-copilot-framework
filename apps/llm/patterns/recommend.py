"""使用大模型进行推荐问题生成

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Optional

from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM


class Recommend(CorePattern):
    """使用大模型进行推荐问题生成"""

    system_prompt: str = ""
    """系统提示词"""

    user_prompt: str = r"""
        根据对话上文、工具描述和用户倾向，生成预测问题。

        信息说明：
        - [Empty]标识空信息，如“工具描述: [Empty]”表示当前未使用工具。
        - 历史提问信息为背景参考作用，最多提供4条。

        生成时需要遵循的要求：
        1. 从用户角度生成预测问题。
        2. 预测问题应为疑问句或祈使句，必须少于30字。
        3. 预测问题应优先贴合工具描述，特别是工具描述与背景或倾向无关时。
        5. 预测问题必须精简，不得输出非必要信息。
        6. 预测问题不得与“用户历史提问”重复或相似。

        ==示例==
        工具描述：调用API，查询天气数据

        用户历史提问：
        - 简单介绍杭州
        - 杭州有哪些著名景点

        用户倾向：
        ['旅游', '美食']

        生成的预测问题：
        杭州西湖景区的门票价格是多少？
        ==结束示例==


        工具描述：{action_description}

        用户历史提问：
        {history_questions}

        用户倾向：
        {user_preference}

        生成的预测问题：
    """
    """用户提示词"""

    def __init__(self, system_prompt: Optional[str] = None, user_prompt: Optional[str] = None) -> None:
        """初始化推荐问题生成Prompt"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, task_id: str, **kwargs) -> str:  # noqa: ANN003
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

        if "shown_questions" not in kwargs or not kwargs["shown_questions"]:
            shown_questions = "[Empty]"
        else:
            shown_questions = kwargs["shown_questions"]

        user_input = self.user_prompt.format(
            action_description=action_description,
            history_questions=history_questions,
            recent_question=kwargs["recent_question"],
            shown_questions=shown_questions,
            user_preference=user_preference,
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]

        result = ""
        async for chunk in ReasoningLLM().call(task_id, messages, streaming=False, temperature=1.0):
            result += chunk

        return result
