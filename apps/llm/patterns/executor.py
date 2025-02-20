"""使用大模型生成Executor的思考内容

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from collections.abc import AsyncGenerator
from textwrap import dedent
from typing import Any, Optional

from apps.entities.scheduler import ExecutorBackground as ExecutorBackgroundEntity
from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM


class ExecutorThought(CorePattern):
    """通过大模型生成Executor的思考内容"""

    system_prompt: str = ""
    """系统提示词"""

    user_prompt: str = r"""
        你是一个可以使用工具的智能助手。请简明扼要地总结工具的使用过程，提供你的见解，并给出下一步的行动。

        你之前使用了一个名为"{tool_name}"的工具，该工具的功能是"{tool_description}"。\
        工具生成的输出是：`{tool_output}`（其中"message"是自然语言内容，"output"是结构化数据）。

        你之前的思考是：
        {last_thought}

        你当前需要解决的问题是：
        {user_question}

        请综合以上信息，再次一步一步地进行思考，并给出见解和行动：
    """
    """用户提示词"""

    def __init__(self, system_prompt: Optional[str] = None, user_prompt: Optional[str] = None) -> None:
        """处理Prompt"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, task_id: str, **kwargs) -> str:  # noqa: ANN003
        """调用大模型，生成对话总结"""
        try:
            last_thought: str = kwargs["last_thought"]
            user_question: str = kwargs["user_question"]
            tool_info: dict[str, Any] = kwargs["tool_info"]
        except Exception as e:
            err = "参数不正确！"
            raise ValueError(err) from e

        messages = [
            {"role": "system", "content": ""},
            {"role": "user", "content": self.user_prompt.format(
                last_thought=last_thought,
                user_question=user_question,
                tool_name=tool_info["name"],
                tool_description=tool_info["description"],
                tool_output=tool_info["output"],
            )},
        ]

        result = ""
        async for chunk in ReasoningLLM().call(task_id, messages, streaming=False, temperature=0.7):
            result += chunk

        return result


class ExecutorBackground(CorePattern):
    """使用大模型进行生成Executor初始背景"""

    system_prompt: str = r""
    """系统提示词"""

    user_prompt: str = r"""
        根据对话上文，结合给定的AI助手思考过程，生成一个完整的背景总结。这个总结将用于后续对话的上下文理解。
        生成总结的要求如下：
        1. 突出重要信息点，例如时间、地点、人物、事件等。
        2. 下面给出的事实条目若与历史记录有关，则可以在生成总结时作为已知信息。
        3. 确保信息准确性，不得编造信息。
        4. 总结应少于1000个字。

        思考过程（在<thought>标签中）：
        {thought}

        关键事实（在<facts>标签中）：
        {facts}

        现在，请开始生成背景总结：
    """
    """用户提示词"""

    def __init__(self, system_prompt: Optional[str] = None, user_prompt: Optional[str] = None) -> None:
        """初始化Background模式"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, task_id: str, **kwargs) -> str:  # noqa: ANN003
        """进行初始背景生成"""
        background: ExecutorBackgroundEntity = kwargs["background"]

        # 转化字符串
        messages = []
        for item in background.conversation:
            messages += [{"role": item["role"], "content": item["content"]}]

        facts_str = "<facts>\n"
        for item in background.facts:
            facts_str += f"- {item}\n"
        facts_str += "</facts>"

        if not background.thought:
            background.thought = "<thought>\n这是新的对话，我还没有思考过。\n</thought>"
        else:
            background.thought = f"<thought>\n{background.thought}\n</thought>"

        messages += [
            {"role": "user", "content": self.user_prompt.format(
                facts=facts_str,
                thought=background.thought,
            )},
        ]

        result = ""
        async for chunk in ReasoningLLM().call(task_id, messages, streaming=False, temperature=1.0):
            result += chunk

        return result


class ExecutorResult(CorePattern):
    """使用大模型生成Executor的最终结果"""

    system_prompt: str = ""
    """系统提示词"""

    user_prompt: str = r"""
        你是AI智能助手，请回答用户的问题并满足以下要求：
        1. 使用中文回答问题，不要使用其他语言。
        2. 回答应当语气友好、通俗易懂，并包含尽可能完整的信息。
        3. 回答时应结合思考过程。

        用户的问题是：
        {question}

        思考过程（在<thought>标签中）：
        <thought>
        {thought}{output}
        </thought>

        现在，请根据以上信息进行回答：
    """
    """用户提示词"""

    def __init__(self, system_prompt: Optional[str] = None, user_prompt: Optional[str] = None) -> None:
        """初始化ExecutorResult模式"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, task_id: str, **kwargs) -> AsyncGenerator[str, None]:  # noqa: ANN003
        """进行ExecutorResult生成"""
        question: str = kwargs["question"]
        thought: str = kwargs["thought"]
        final_output: dict[str, Any] = kwargs.get("final_output", {})

        # 如果final_output不为空，则将final_output转换为字符串
        if final_output:
            final_output_str = dedent(f"""
                工具提供了{final_output['type']}类型数据：`{final_output['data']}`。\
                这些数据已经使用恰当的办法向用户进行了展示，所以无需重复。\
                若类型为“schema”，说明用户的问题缺少回答所需的必要信息。\
                我需要根据schema的具体内容分析缺失哪些信息，并提示用户补充。
            """)
        else:
            final_output_str = ""

        user_input = self.user_prompt.format(
            question=question,
            thought=thought,
            output=final_output_str,
        )
        messages = [
            {"role": "system", "content": ""},
            {"role": "user", "content": user_input},
        ]

        async for chunk in ReasoningLLM().call(task_id, messages, streaming=True, temperature=0.7):
            yield chunk
