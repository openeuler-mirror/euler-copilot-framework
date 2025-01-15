"""使用大模型生成Executor的思考内容

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from collections.abc import AsyncGenerator
from textwrap import dedent
from typing import Any, Optional

from apps.entities.plugin import ExecutorBackground as ExecutorBackgroundEntity
from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM


class ExecutorThought(CorePattern):
    """通过大模型生成Executor的思考内容"""

    system_prompt: str = r"""
        You are an intelligent assistant equipped with tools to access necessary information.
        Your task is to: succinctly summarize the tool usage process, provide your insights, and propose the next logical action.
    """
    """系统提示词"""

    user_prompt: str = r"""
        You previously utilized a tool named "{tool_name}" which performs the function of "{tool_description}". \
        The tool's generated output is: `{tool_output}` (with "message" as the natural language content and "output" as structured data).

        Your earlier thoughts were:
        {last_thought}

        The current question you seek to resolve is:
        {user_question}

        Consider the above information thoroughly; articulate your thoughts methodically, step by step.
        Begin.
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
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(
                last_thought=last_thought,
                user_question=user_question,
                tool_name=tool_info["name"],
                tool_description=tool_info["description"],
                tool_output=tool_info["output"],
            )},
        ]

        result = ""
        async for chunk in ReasoningLLM().call(task_id, messages, streaming=False, temperature=1.0):
            result += chunk

        return result


class ExecutorBackground(CorePattern):
    """使用大模型进行生成Executor初始背景"""

    system_prompt: str = r"""
        你是一位专门负责总结和分析对话的AI助手。你的任务是：
        1. 理解用户与AI之间的对话内容
        2. 分析提供的关键事实列表
        3. 结合之前的思考生成一个简洁但全面的背景总结
        4. 确保总结包含对话中的重要信息点和关键概念
        请用清晰、专业的语言输出总结，同时注意呈现预先考虑过的思考内容。
    """
    """系统提示词"""

    user_prompt: str = r"""
        请分析以下内容：

        1. 之前的思考：
        <thought>
        {thought}
        </thought>

        2. 对话记录（包含用户和AI的对话，在<conversation>标签中）：
        <conversation>
        {conversation}
        </conversation>

        3. 关键事实（在<facts>标签中）：
        <facts>
        {facts}
        </facts>

        请基于以上信息，生成一个完整的背景总结。这个总结将用于后续对话的上下文理解。
        要求：
        - 突出重要信息点
        - 保持逻辑连贯性
        - 确保信息准确性
        请开始总结。
    """
    """用户提示词"""

    def __init__(self, system_prompt: Optional[str] = None, user_prompt: Optional[str] = None) -> None:
        """初始化Background模式"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, task_id: str, **kwargs) -> str:  # noqa: ANN003
        """进行初始背景生成"""
        background: ExecutorBackgroundEntity = kwargs["background"]

        # 转化字符串
        message_str = ""
        for item in background.conversation:
            message_str += f"[{item['role']}] {item['content']}\n"
        facts_str = ""
        for item in background.facts:
            facts_str += f"- {item}\n"
        if not background.thought:
            background.thought = "这是新的对话，我还没有思考过。"

        user_input = self.user_prompt.format(
            conversation=message_str,
            facts=facts_str,
            thought=background.thought,
        )
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]

        result = ""
        async for chunk in ReasoningLLM().call(task_id, messages, streaming=False, temperature=1.0):
            result += chunk

        return result


class ExecutorResult(CorePattern):
    """使用大模型生成Executor的最终结果"""

    system_prompt: str = r"""
        你是一个专业的智能助手，旨在根据背景信息等，回答用户的问题。

        要求：
        - 使用中文回答问题，不要使用其他语言。
        - 提供的回答应当语气友好、通俗易懂，并包含尽可能完整的信息。
    """
    """系统提示词"""

    user_prompt: str = r"""
        用户的问题是：
        {question}

        以下是一些供参考的背景信息：
        {thought}
        {final_output}

        现在，请根据以上信息，针对用户的问题提供准确而简洁的回答。
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
                你提供了{final_output['type']}类型数据：`{final_output['data']}`。\
                这些数据已经使用恰当的办法向用户进行了展示，所以无需重复展示。\
                当类型为“schema”时，证明用户的问题缺少回答所需的必要信息。\
                我需要根据Schema的具体内容分析缺失哪些信息，并提示用户补充。
            """)
        else:
            final_output_str = ""

        user_input = self.user_prompt.format(
            question=question,
            thought=thought,
            final_output=final_output_str,
        )
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]

        async for chunk in ReasoningLLM().call(task_id, messages, streaming=True, temperature=1.0):
            yield chunk
