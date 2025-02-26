"""工具：调用大模型

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from datetime import datetime
from textwrap import dedent
from typing import Any, ClassVar

import pytz
from jinja2 import BaseLoader, select_autoescape
from jinja2.sandbox import SandboxedEnvironment
from pydantic import BaseModel, Field

from apps.entities.scheduler import CallError, CallVars
from apps.llm.reasoning import ReasoningLLM
from apps.scheduler.call.core import CoreCall

LLM_DEFAULT_PROMPT = dedent(
    r"""
        <instructions>
            你是一个乐于助人的智能助手。请结合给出的背景信息, 回答用户的提问。
            当前时间：{{ time }}，可以作为时间参照。
            用户的问题将在<user_question>中给出，上下文背景信息将在<context>中给出。
            注意：输出不要包含任何XML标签，不要编造任何信息。若你认为用户提问与背景信息无关，请忽略背景信息直接作答。
        </instructions>

        <user_question>
            {{ question }}
        </user_question>

        <context>
            {{ context }}
        </context>
    """,
    ).strip("\n")


class LLMNodeOutput(BaseModel):
    """定义LLM工具调用的输出"""

    message: str = Field(description="大模型输出的文字信息")


class LLM(CoreCall, ret_type=LLMNodeOutput):
    """大模型调用工具"""

    name: ClassVar[str] = "大模型"
    description: ClassVar[str] = "以指定的提示词和上下文信息调用大模型，并获得输出。"

    temperature: float = Field(description="大模型温度（随机化程度）", default=0.7)
    enable_context: bool = Field(description="是否启用上下文", default=True)
    system_prompt: str = Field(description="大模型系统提示词", default="")
    user_prompt: str = Field(description="大模型用户提示词", default=LLM_DEFAULT_PROMPT)

    async def __call__(self, syscall_vars: CallVars, **_kwargs: Any) -> LLMNodeOutput:
        """运行LLM Call"""
        # 参数
        time = datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        formatter = {
            "time": time,
            "context": syscall_vars.background,
            "question": syscall_vars.question,
        }

        try:
            # 准备系统提示词
            system_tmpl = SandboxedEnvironment(
                loader=BaseLoader(),
                autoescape=select_autoescape(),
                trim_blocks=True,
                lstrip_blocks=True,
            ).from_string(self.system_prompt)
            system_input = system_tmpl.render(**formatter)

            # 准备用户提示词
            user_tmpl = SandboxedEnvironment(
                loader=BaseLoader(),
                autoescape=select_autoescape(),
                trim_blocks=True,
                lstrip_blocks=True,
            ).from_string(self.user_prompt)
            user_input = user_tmpl.render(**formatter)
        except Exception as e:
            raise CallError(message=f"用户提示词渲染失败：{e!s}", data={}) from e

        message = [
            {"role": "system", "content": system_input},
            {"role": "user", "content": user_input},
        ]

        try:
            result = ""
            async for chunk in ReasoningLLM().call(task_id=syscall_vars.task_id, messages=message):
                result += chunk
        except Exception as e:
            raise CallError(message=f"大模型调用失败：{e!s}", data={}) from e

        return LLMNodeOutput(message=result)
