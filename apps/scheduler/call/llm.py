"""工具：调用大模型

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from datetime import datetime
from textwrap import dedent
from typing import Any

import pytz
from jinja2 import BaseLoader, select_autoescape
from jinja2.sandbox import SandboxedEnvironment
from pydantic import BaseModel, Field

from apps.entities.plugin import CallError, SysCallVars
from apps.llm.reasoning import ReasoningLLM
from apps.scheduler.call.core import CoreCall


class _LLMParams(BaseModel):
    """LLMParams类用于定义大模型调用的参数，包括温度设置、系统提示词、用户提示词和超时时间。

    属性:
        temperature (float): 大模型温度设置，默认值是1.0。
        system_prompt (str): 大模型系统提示词。
        user_prompt (str): 大模型用户提示词。
        timeout (int): 超时时间，默认值是30秒。
    """

    temperature: float = Field(description="大模型温度设置", default=1.0)
    system_prompt: str = Field(description="大模型系统提示词", default="你是一个乐于助人的助手。")
    user_prompt: str = Field(
        description="大模型用户提示词",
        default=dedent("""
                        回答下面的用户问题：
                        {{ question }}

                        附加信息：
                        当前时间为{{ time }}。用户在提问前，使用了工具，并获得了以下返回值：`{{ last.output }}`。
                        额外的背景信息：{{ context }}
            """).strip("\n"))
    timeout: int = Field(description="超时时间", default=30)


class _LLMOutput(BaseModel):
    """定义LLM工具调用的输出"""

    message: str = Field(description="大模型输出的文字信息")


class LLM(metaclass=CoreCall, param_cls=_LLMParams, output_cls=_LLMOutput):
    """大模型调用工具"""

    name: str = "llm"
    description: str = "大模型调用工具，用于以指定的提示词和上下文信息调用大模型，并获得输出。"


    async def __call__(self, _slot_data: dict[str, Any]) -> _LLMOutput:
        """运行LLM Call"""
        # 获取必要参数
        syscall_vars: SysCallVars = getattr(self, "_syscall_vars")
        params: _LLMParams = getattr(self, "_params")
        # 参数
        time = datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        formatter = {
            "time": time,
            "context": syscall_vars.background,
            "question": syscall_vars.question,
            "history": syscall_vars.history,
        }

        try:
            # 准备提示词
            system_tmpl = SandboxedEnvironment(
                loader=BaseLoader(),
                autoescape=select_autoescape(),
                trim_blocks=True,
                lstrip_blocks=True,
            ).from_string(params.system_prompt)
            system_input = system_tmpl.render(**formatter)
            user_tmpl = SandboxedEnvironment(
                loader=BaseLoader(),
                autoescape=select_autoescape(),
                trim_blocks=True,
                lstrip_blocks=True,
            ).from_string(params.user_prompt)
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

        return _LLMOutput(message=result)
