"""使用大模型多轮投票，选择最优选项

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import asyncio
import json
from collections import Counter
from typing import Any, ClassVar, Optional

from apps.llm.patterns.core import CorePattern
from apps.llm.patterns.json import Json
from apps.llm.reasoning import ReasoningLLM


class Select(CorePattern):
    """通过投票选择最佳答案"""

    system_prompt: str = r"""
        Your task is: select the best option from the list of available options. The option should be able to answer \
        the question and be inferred from the context and the output.

        EXAMPLE
        Question: 使用天气API，查询明天杭州的天气信息

        Context: 人类首先询问了杭州有什么美食，之后询问了杭州有什么知名旅游景点。

        Output: `{}`

        The available options are:
        - API: 请求特定API，获得返回的JSON数据
        - SQL: 查询数据库，获得数据库表中的数据

        Let's think step by step. API tools can retrieve external data through the use of APIs, and weather \
        information may be stored in external data. As the user instructions explicitly mentioned the use of the weather API, \
        the API tool should be prioritized. SQL tools are used to retrieve information from databases. Given the variable \
        and dynamic nature of weather data, it is unlikely to be stored in a database. Therefore, the priority of \
        SQL tools is relatively low. The best option seems to be "API: request a specific API, get the \
        returned JSON data".
        END OF EXAMPLE

        Let's begin.
    """
    """系统提示词"""

    user_prompt: str = r"""
        Question: {question}

        Context: {background}

        Output: `{data}`

        The available options are:
        {choice_list}

        Let's think step by step.
    """
    """用户提示词"""

    slot_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "choice": {
                "type": "string",
                "description": "The choice of the option.",
            },
        },
        "required": ["choice"],
    }
    """最终输出的JSON Schema"""

    def __init__(self, system_prompt: Optional[str] = None, user_prompt: Optional[str] = None) -> None:
        """初始化Prompt"""
        super().__init__(system_prompt, user_prompt)

    @staticmethod
    def _choices_to_prompt(choices: list[dict[str, Any]]) -> tuple[str, list[str]]:
        """将选项转换为Prompt"""
        choices_prompt = ""
        choice_str_list = []
        for choice in choices:
            choices_prompt += "- {}: {}\n".format(choice["branch"], choice["description"])
            choice_str_list.append(choice["branch"])
        return choices_prompt, choice_str_list

    async def _generate_single_attempt(self, task_id: str, user_input: str, choice_list: list[str]) -> str:
        """使用ReasoningLLM进行单次尝试"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]
        result = ""
        async for chunk in ReasoningLLM().call(task_id, messages, streaming=False):
            result += chunk
        # 使用FunctionLLM进行参数提取
        schema = self.slot_schema
        schema["properties"]["choice"]["enum"] = choice_list

        messages += [{"role": "assistant", "content": result}]
        function_result = await Json().generate(task_id, conversation=messages, spec=schema)
        return function_result["choice"]

    async def generate(self, task_id: str, **kwargs) -> str:  # noqa: ANN003
        """使用大模型做出选择"""
        max_try = 3
        result_list = []

        background = kwargs.get("background", "无背景信息。")
        data_str = json.dumps(kwargs.get("data", {}), ensure_ascii=False)

        choice_prompt, choices_list = self._choices_to_prompt(kwargs["choices"])
        user_input = self.user_prompt.format(
            question=kwargs["question"],
            background=background,
            data=data_str,
            choice_list=choice_prompt,
        )

        result_coroutine = [self._generate_single_attempt(task_id, user_input, choices_list) for _ in range(max_try)]
        result_list = await asyncio.gather(*result_coroutine)

        count = Counter(result_list)
        return count.most_common(1)[0][0]
