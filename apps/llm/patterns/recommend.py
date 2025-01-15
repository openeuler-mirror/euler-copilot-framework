"""使用大模型进行推荐问题生成

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Optional

from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM


class Recommend(CorePattern):
    """使用大模型进行推荐问题生成"""

    system_prompt: str = r"""
        你是智能助手，负责分析问答历史并预测用户问题。

        **任务说明：**
        - 根据背景信息、工具描述和用户倾向预测问题。

        **信息说明：**
        - [Empty]标识空信息，如“背景信息: [Empty]”表示当前无背景信息。
        - 背景信息含最近1条完整问答信息及最多4条历史提问信息。

        **要求：**
        1. 用用户口吻生成问题。
        2. 优先使用工具描述进行预测，特别是与背景或倾向无关时。
        3. 工具描述为空时，依据背景和倾向预测。
        4. 生成的应为疑问句或祈使句，时间限制为30字。
        5. 避免输出非必要信息。
        6. 新生成的问题不得与“已展示问题”或“用户历史提问”重复或相似。

        **示例：**

        EXAMPLE 1
        ## 工具描述
        调用API，查询天气数据

        ## 背景信息
        ### 用户历史提问
        Question 1: 简单介绍杭州
        Question 2: 杭州有哪些著名景点

        ### 最近1轮问答
        Question: 帮我查询今天的杭州天气数据
        Answer: 杭州今天晴，气温20度，空气质量优。

        ## 用户倾向
        ['旅游', '美食']

        ## 已展示问题
        杭州有什么好吃的？

        ## 预测问题
        杭州西湖景区的门票价格是多少？
        END OF EXAMPLE 1

        EXAMPLE 2
        ## 工具描述
        [Empty]

        ## 背景信息
        ### 用户历史提问
        [Empty]

        ### 最近1轮问答
        Question: 帮我查询上周的销售数据
        Answer: 上周的销售数据如下：
        星期一：1000
        星期二：1200
        星期三：1100
        星期四：1300
        星期五：1400

        ## 用户倾向
        ['销售', '数据分析']

        ## 已展示问题
        [Empty]

        ## 预测问题
        帮我分析上周的销售数据趋势
        END OF EXAMPLE 2

        Let's begin.
    """
    """系统提示词"""

    user_prompt: str = r"""
        ## 工具描述
        {action_description}

        ## 背景信息
        ### 用户历史提问
        {history_questions}

        ### 最近1轮问答
        {recent_question}

        ## 用户倾向
        {user_preference}

        ## 已展示问题
        {shown_questions}

        ## 预测问题
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
