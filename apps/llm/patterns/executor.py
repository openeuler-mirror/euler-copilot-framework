"""使用大模型生成Executor的思考内容

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, Optional

from apps.entities.scheduler import ExecutorBackground
from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM


class ExecutorThought(CorePattern):
    """通过大模型生成Executor的思考内容"""

    user_prompt: str = r"""
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


class ExecutorSummary(CorePattern):
    """使用大模型进行生成Executor初始背景"""

    user_prompt: str = r"""
        <instructions>
            根据给定的AI助手思考过程和关键事实，生成一个三句话背景总结。这个总结将用于后续对话的上下文理解。

            生成总结的要求如下：
            1. 突出重要信息点，例如时间、地点、人物、事件等。
            2. “关键事实”中的内容可在生成总结时作为已知信息。
            3. 输出时请不要包含XML标签，确保信息准确性，不得编造信息。
            4. 总结应少于3句话，应少于300个字。

            AI助手思考过程将在<thought>标签中给出，关键事实将在<facts>标签中给出。
        </instructions>

        <thought>
            {thought}
        </thought>

        <facts>
            {facts}
        </facts>

        现在，请开始生成背景总结：
    """
    """用户提示词"""

    def __init__(self, system_prompt: Optional[str] = None, user_prompt: Optional[str] = None) -> None:
        """初始化Background模式"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, task_id: str, **kwargs) -> str:  # noqa: ANN003
        """进行初始背景生成"""
        background: ExecutorBackground = kwargs["background"]

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
