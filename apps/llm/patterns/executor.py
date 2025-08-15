# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""使用大模型生成Executor的思考内容"""

from typing import TYPE_CHECKING, Any

from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM
from apps.llm.snippet import convert_context_to_prompt, facts_to_prompt
from apps.schemas.enum_var import LanguageType
if TYPE_CHECKING:
    from apps.schemas.scheduler import ExecutorBackground


class ExecutorThought(CorePattern):
    """通过大模型生成Executor的思考内容"""

    user_prompt: dict[LanguageType, str] = {
        LanguageType.CHINESE: r"""
        <instructions>
            <instruction>
                你是一个可以使用工具的智能助手。
                在回答用户的问题时，你为了获取更多的信息，使用了一个工具。
                请简明扼要地总结工具的使用过程，提供你的见解，并给出下一步的行动。

                注意：
                工具的相关信息在<tool></tool>标签中给出。
                为了使你更好的理解发生了什么，你之前的思考过程在<thought></thought>标签中给出。
                输出时请不要包含XML标签，输出时请保持简明和清晰。
            </instruction>
        </instructions>

        <tool>
            <name>{tool_name}</name>
            <description>{tool_description}</description>
            <output>{tool_output}</output>
        </tool>

        <thought>
            {last_thought}
        </thought>

        <question>
            你当前需要解决的问题是：
            {user_question}
        </question>

        请综合以上信息，再次一步一步地进行思考，并给出见解和行动：
    """,
        LanguageType.ENGLISH: r"""
        <instructions>
            <instruction>
                You are an intelligent assistant who can use tools.
                When answering user questions, you use a tool to get more information.
                Please summarize the process of using the tool briefly, provide your insights, and give the next action.

                Note:
                The information about the tool is given in the <tool></tool> tag.
                To help you better understand what happened, your previous thought process is given in the <thought></thought> tag.
                Do not include XML tags in the output, and keep the output brief and clear.
            </instruction>
        </instructions>

        <tool>
            <name>{tool_name}</name>
            <description>{tool_description}</description>
            <output>{tool_output}</output>
        </tool>

        <thought>
            {last_thought}
        </thought>

        <question>
            The question you need to solve is:
            {user_question}
        </question>

        Please integrate the above information, think step by step again, provide insights, and give actions:
    """,
    }
    """用户提示词"""

    def __init__(
        self,
        system_prompt: dict[LanguageType, str] | None = None,
        user_prompt: dict[LanguageType, str] | None = None,
    ) -> None:
        """处理Prompt"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, **kwargs) -> str:  # noqa: ANN003
        """调用大模型，生成对话总结"""
        try:
            last_thought: str = kwargs["last_thought"]
            user_question: str = kwargs["user_question"]
            tool_info: dict[str, Any] = kwargs["tool_info"]
            language: LanguageType = kwargs.get("language", LanguageType.CHINESE)
        except Exception as e:
            err = "参数不正确！"
            raise ValueError(err) from e

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": self.user_prompt[language].format(
                    last_thought=last_thought,
                    user_question=user_question,
                    tool_name=tool_info["name"],
                    tool_description=tool_info["description"],
                    tool_output=tool_info["output"],
                ),
            },
        ]

        llm = ReasoningLLM()
        result = ""
        async for chunk in llm.call(messages, streaming=False, temperature=0.7):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        return result


class ExecutorSummary(CorePattern):
    """使用大模型进行生成Executor初始背景"""

    user_prompt: dict[LanguageType, str] = {
        LanguageType.CHINESE: r"""
        <instructions>
            根据给定的对话记录和关键事实，生成一个三句话背景总结。这个总结将用于后续对话的上下文理解。

            生成总结的要求如下：
            1. 突出重要信息点，例如时间、地点、人物、事件等。
            2. “关键事实”中的内容可在生成总结时作为已知信息。
            3. 输出时请不要包含XML标签，确保信息准确性，不得编造信息。
            4. 总结应少于3句话，应少于300个字。

            对话记录将在<conversation>标签中给出，关键事实将在<facts>标签中给出。
        </instructions>

        {conversation}

        <facts>
            {facts}
        </facts>

        现在，请开始生成背景总结：
    """,
        LanguageType.ENGLISH: r"""
        <instructions>
            Based on the given conversation records and key facts, generate a three-sentence background summary. This summary will be used for context understanding in subsequent conversations.

            The requirements for generating the summary are as follows:
            1. Highlight important information points, such as time, location, people, events, etc.
            2. The content in the "key facts" can be used as known information when generating the summary.
            3. Do not include XML tags in the output, ensure the accuracy of the information, and do not make up information.
            4. The summary should be less than 3 sentences and less than 300 words.

            The conversation records will be given in the <conversation> tag, and the key facts will be given in the <facts> tag.
        </instructions>

        {conversation}

        <facts>
            {facts}
        </facts>

        Now, please start generating the background summary:
    """,
    }
    """用户提示词"""

    def __init__(
        self,
        system_prompt: dict[LanguageType, str] | None = None,
        user_prompt: dict[LanguageType, str] | None = None,
    ) -> None:
        """初始化Background模式"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, **kwargs) -> str:  # noqa: ANN003
        """进行初始背景生成"""
        background: ExecutorBackground = kwargs["background"]
        conversation_str = convert_context_to_prompt(background.conversation)
        facts_str = facts_to_prompt(background.facts)
        language = kwargs.get("language", LanguageType.CHINESE)

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": self.user_prompt[language].format(
                    facts=facts_str,
                    conversation=conversation_str,
                ),
            },
        ]

        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False, temperature=0.7):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        return result.strip().strip("\n")
