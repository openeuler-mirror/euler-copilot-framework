# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""使用大模型多轮投票，选择最优选项"""

import asyncio
import json
import logging
from collections import Counter
from typing import Any, ClassVar

from apps.llm.function import JsonGenerator
from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM
from apps.llm.snippet import choices_to_prompt
from apps.schemas.enum_var import LanguageType

logger = logging.getLogger(__name__)


class Select(CorePattern):
    """通过投票选择最佳答案"""

    system_prompt: dict[LanguageType, str] = {
        LanguageType.CHINESE: "你是一个有用的助手。",
        LanguageType.ENGLISH: "You are a helpful assistant.",
    }
    """系统提示词"""

    user_prompt: dict[LanguageType, str] = {
        LanguageType.CHINESE: r"""
        <instructions>
            <instruction>
                根据历史对话（包括工具调用结果）和用户问题，从给出的选项列表中，选出最符合要求的那一项。
                在输出之前，请先思考，并使用“<think>”标签给出思考过程。
                结果需要使用JSON格式输出，输出格式为：{{ "choice": "选项名称" }}
            </instruction>

            <example>
                <input>
                    <question>使用天气API，查询明天杭州的天气信息</question>

                    <options>
                        <item>
                            <name>API</name>
                            <description>HTTP请求，获得返回的JSON数据</description>
                        </item>
                        <item>
                            <name>SQL</name>
                            <description>查询数据库，获得数据库表中的数据</description>
                        </item>
                    </options>
                </input>

                <reasoning>
                    API 工具可以通过 API 来获取外部数据，而天气信息可能就存储在外部数据中，由于用户说明中明确提到了 \
                    天气 API 的使用，因此应该优先使用 API 工具。\
                    SQL 工具用于从数据库中获取信息，考虑到天气数据的可变性和动态性，不太可能存储在数据库中，因此 \
                    SQL 工具的优先级相对较低，\
                    最佳选择似乎是“API：请求特定 API，获取返回的 JSON 数据”。
                </reasoning>

                <output>
                    {{ "choice": "API" }}
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
    """,
        LanguageType.ENGLISH: r"""
        <instructions>
            <instruction>
                Based on the historical dialogue (including tool call results) and user question, select the most \
                suitable option from the given option list.
                Before outputting, please think carefully and use the "<think>" tag to give the thinking process.
                The output needs to be in JSON format, the output format is: {{ "choice": "option name" }}
            </instruction>

            <example>
                <input>
                    <question>Use the weather API to query the weather information of Hangzhou tomorrow</question>

                    <options>
                        <item>
                            <name>API</name>
                            <description>HTTP request, get the returned JSON data</description>
                        </item>
                        <item>
                            <name>SQL</name>
                            <description>Query the database, get the data in the database table</description>
                        </item>
                    </options>
                </input>

                <reasoning>
                    The API tool can get external data through API, and the weather information may be stored in \
                    external data. Since the user clearly mentioned the use of weather API, it should be given \
                    priority to the API tool.\
                    The SQL tool is used to get information from the database, considering the variability and \
                    dynamism of weather data, it is unlikely to be stored in the database, so the priority of \
                    the SQL tool is relatively low, \
                    The best choice seems to be "API: request a specific API, get the returned JSON data".
                </reasoning>

                <output>
                    {{ "choice": "API" }}
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
                Let's think step by step.
            </reasoning>
        </input>
    """,
    }
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

    def __init__(
        self,
        system_prompt: dict[LanguageType, str] | None = None,
        user_prompt: dict[str, str] | None = None,
    ) -> None:
        """处理Prompt"""
        super().__init__(system_prompt, user_prompt)

    async def _generate_single_attempt(self, user_input: str, choice_list: list[str]) -> str:
        """使用ReasoningLLM进行单次尝试"""
        logger.info("[Select] 单次选择尝试: %s", user_input)
        messages = [
            {"role": "system", "content": self.system_prompt[self.language]},
            {"role": "user", "content": user_input},
        ]
        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens
        logger.info("[Select] 选择结果: %s", result)

        # 使用FunctionLLM进行参数提取
        schema = self.slot_schema
        schema["properties"]["choice"]["enum"] = choice_list

        messages += [{"role": "assistant", "content": result}]
        json_gen = JsonGenerator(
            query="根据给定的背景信息，生成预测问题",
            conversation=messages,
            schema=schema,
        )
        function_result = await json_gen.generate()
        return function_result["choice"]


    async def generate(self, **kwargs) -> str:  # noqa: ANN003
        """使用大模型做出选择"""
        logger.info("[Select] 使用LLM选择")
        max_try = 3
        result_list = []

        background = kwargs.get("background", "无背景信息。")
        self.language = kwargs.get("language", LanguageType.CHINESE)
        data_str = json.dumps(kwargs.get("data", {}), ensure_ascii=False)

        choice_prompt, choices_list = choices_to_prompt(kwargs["choices"])

        if not choices_list:
            error_msg = "[Select] 选项列表不能为空"
            logger.error(error_msg)
            raise ValueError(error_msg)
        if len(choices_list) == 1:
            logger.info("[Select] 选项列表只有一个选项，直接返回")
            return choices_list[0]

        logger.info("[Select] 选项列表: %s", choice_prompt)
        user_input = self.user_prompt[self.language].format(
            question=kwargs["question"],
            background=background,
            data=data_str,
            choice_list=choice_prompt,
        )

        result_coroutine = [self._generate_single_attempt(user_input, choices_list) for _ in range(max_try)]
        result_list = await asyncio.gather(*result_coroutine)

        count = Counter(result_list)
        selected_choice = count.most_common(1)[0][0]

        logger.info("[Select] 选择结果: %s", selected_choice)
        return selected_choice
