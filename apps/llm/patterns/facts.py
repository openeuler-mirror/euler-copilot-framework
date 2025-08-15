# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""事实提取"""

import logging

from pydantic import BaseModel, Field

from apps.llm.function import JsonGenerator
from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM
from apps.llm.snippet import convert_context_to_prompt
from apps.schemas.enum_var import LanguageType

logger = logging.getLogger(__name__)


class FactsResult(BaseModel):
    """事实提取结果"""

    facts: list[str] = Field(description="从对话中提取的事实列表，可以为空")


class Facts(CorePattern):
    """事实提取"""

    system_prompt: str = "You are a helpful assistant."
    """系统提示词（暂不使用）"""

    user_prompt: dict[LanguageType, str] = {
        LanguageType.CHINESE: r"""
        <instructions>
            <instruction>
                从对话中提取关键信息，并将它们组织成独一无二的、易于理解的事实，包含用户偏好、关系、实体等有用信息。
                以下是需要关注的信息类型以及有关如何处理输入数据的详细说明。

                **你需要关注的信息类型**
                1. 实体：对话中涉及到的实体。例如：姓名、地点、组织、事件等。
                2. 偏好：对待实体的态度。例如喜欢、讨厌等。
                3. 关系：用户与实体之间，或两个实体之间的关系。例如包含、并列、互斥等。
                4. 动作：对实体产生影响的具体动作。例如查询、搜索、浏览、点击等。

                **要求**
                1. 事实必须准确，只能从对话中提取。不要将样例中的信息体现在输出中。
                2. 事实必须清晰、简洁、易于理解。必须少于30个字。
                3. 必须按照以下JSON格式输出：

                {{
                    "facts": ["事实1", "事实2", "事实3"]
                }}
            </instruction>

            <example>
                <conversation>
                    <user>杭州西湖有哪些景点？</user>
                    <assistant>杭州西湖是中国浙江省杭州市的一个著名景点，以其美丽的自然风光和丰富的文化遗产而闻名。西湖周围有许多著名的景点，包括著名的苏堤、白堤、断桥、三潭印月等。西湖以其清澈的湖水和周围的山脉而著名，是中国最著名的湖泊之一。</assistant>
                </conversation>

                <output>
                    {{
                        "facts": ["杭州西湖有苏堤、白堤、断桥、三潭印月等景点"]
                    }}
                </output>
            </example>
        </instructions>

        {conversation}
        <output>
    """,
        LanguageType.ENGLISH: r"""
        <instructions>
            <instruction>
                Extract key information from the conversation and organize it into unique, easily understandable facts that include user preferences, relationships, entities, etc.
                The following are the types of information to be paid attention to and detailed instructions on how to handle the input data.

                **Types of information to be paid attention to**
                1. Entities: Entities involved in the conversation. For example: names, locations, organizations, events, etc.
                2. Preferences: Attitudes towards entities. For example: like, dislike, etc.
                3. Relationships: Relationships between the user and entities, or between two entities. For example: include, parallel, exclusive, etc.
                4. Actions: Specific actions that affect entities. For example: query, search, browse, click, etc.

                **Requirements**
                1. Facts must be accurate and can only be extracted from the conversation. Do not include information from the sample in the output.
                2. Facts must be clear, concise, and easy to understand. Must be less than 30 words.
                3. Output in the following JSON format:

                {{
                    "facts": ["fact1", "fact2", "fact3"]
                }}
            </instruction>

            <example>
                <conversation>
                    <user>What are the attractions in West Lake, Hangzhou?</user>
                    <assistant>West Lake in Hangzhou is a famous scenic spot in Hangzhou, Zhejiang Province, China, famous for its beautiful natural scenery and rich cultural heritage. There are many famous attractions around West Lake, including the famous Su Causeway, Bai Causeway, Broken Bridge, Three Pools Mirroring the Moon, etc. West Lake is famous for its clear water and surrounding mountains, and is one of the most famous lakes in China. </assistant>
                </conversation>

                <output>
                    {{
                        "facts": ["West Lake has the famous attractions of Suzhou Embankment, Bai Embankment, Qiantang Bridge, San Tang Yin Yue, etc."]
                    }}
                </output>
            </example>
        </instructions>

        {conversation}
        <output>    
    """,
    }
    """用户提示词"""

    def __init__(
        self,
        system_prompt: dict[LanguageType, str] | None = None,
        user_prompt: dict[LanguageType, str] | None = None,
    ) -> None:
        """初始化Prompt"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, **kwargs) -> list[str]:  # noqa: ANN003
        """事实提取"""
        conversation = convert_context_to_prompt(kwargs["conversation"])
        language = kwargs.get("language", LanguageType.CHINESE)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt[language].format(conversation=conversation)},
        ]
        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        messages += [{"role": "assistant", "content": result}]
        json_gen = JsonGenerator(
            query="根据给定的背景信息，提取事实条目",
            conversation=messages,
            schema=FactsResult.model_json_schema(),
        )

        try:
            fact_dict = FactsResult.model_validate(await json_gen.generate())
        except Exception:
            logger.exception("[Facts] 事实提取失败")
            return []

        return fact_dict.facts
