"""使用大模型多轮投票，选择最优选项

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import asyncio
import json
from collections import Counter
from typing import Any, ClassVar, Optional

from apps.constants import LOGGER
from apps.llm.patterns.core import CorePattern
from apps.llm.patterns.json import Json
from apps.llm.reasoning import ReasoningLLM


class Select(CorePattern):
    """通过投票选择最佳答案"""

    user_prompt: str = r"""
        <instructions>
            <instruction>
                根据历史对话（包括工具调用结果）和用户问题，从给出的选项列表中，选出最符合要求的那一项。
                在输出之前，请先思考，并使用“<think>”标签给出思考过程。
                结果需要使用JSON格式输出，输出格式为：{ "choice": "选项名称" }
            </instruction>

            <example>
                <input>
                    <question>使用天气API，查询明天杭州的天气信息</question>

                    <options>
                        <item>[API] 请求特定API，获得返回的JSON数据</item>
                        <item>[SQL] 查询数据库，获得数据库表中的数据</item>
                    </options>
                </input>

                <reasoning>
                    API 工具可以通过 API 来获取外部数据，而天气信息可能就存储在外部数据中，由于用户说明中明确提到了天气 API 的使用，因此应该优先使用 API 工具。\
                    SQL 工具用于从数据库中获取信息，考虑到天气数据的可变性和动态性，不太可能存储在数据库中，因此 SQL 工具的优先级相对较低，\
                    最佳选择似乎是“API：请求特定 API，获取返回的 JSON 数据”。
                </reasoning>

                <output>
                    { "choice": "API" }
                </output>
            </example>
        </instructions>

        <input>
            <question>
                {question}
            </question>

            <options>
                {choice_list}
            </options>
        </input>

        <reasoning>
          让我们一步一步思考。
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
            choices_prompt += "- {}: {}\n".format(choice["name"], choice["description"])
            choice_str_list.append(choice["name"])
        return choices_prompt, choice_str_list


    async def _generate_single_attempt(self, task_id: str, user_input: str, choice_list: list[str]) -> str:
        """使用ReasoningLLM进行单次尝试"""
        LOGGER.info(f"[Select] Trying single attempt for task {task_id}...")
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]
        result = ""
        async for chunk in ReasoningLLM().call(task_id, messages, streaming=False):
            result += chunk
        LOGGER.info(f"[Select] Result: {result}")

        # 使用FunctionLLM进行参数提取
        schema = self.slot_schema
        schema["properties"]["choice"]["enum"] = choice_list

        messages += [{"role": "assistant", "content": result}]
        function_result = await Json().generate("", conversation=messages, spec=schema)
        return function_result["choice"]


    async def generate(self, task_id: str, **kwargs) -> str:  # noqa: ANN003
        """使用大模型做出选择"""
        LOGGER.info(f"[Select] Selecting using LLM: {task_id}...")
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
        LOGGER.info(f"[Select] Result: {count.most_common(1)[0][0]}")
        return count.most_common(1)[0][0]
