"""工具：调用大模型

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from collections.abc import AsyncGenerator
from datetime import datetime
from textwrap import dedent
from typing import Any, ClassVar

import pytz
from jinja2 import BaseLoader, select_autoescape
from jinja2.sandbox import SandboxedEnvironment
from pydantic import BaseModel, Field

from apps.entities.plugin import CallError, CallResult, SysCallVars
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
    output_to_user: bool = Field(description="是否将输出推送给用户", default=True)


class LLM(CoreCall):
    """大模型调用工具"""

    def __init__(self, syscall_vars: SysCallVars, **kwargs) -> None:  # noqa: ANN003
        """初始化LLM Call"""
        self._core_params = syscall_vars
        self._params = _LLMParams.model_validate(kwargs)
        # 初始化Slot Schema
        self.slot_schema = {}


    name: str = "llm"
    description: str = "大模型调用工具，用于以指定的提示词和上下文信息调用大模型，并获得输出。"
    params_schema: ClassVar[dict[str, Any]] = _LLMParams.model_json_schema()


    async def _prepare_message(self) -> list[dict[str, str]]:
        """准备消息"""
        # 获取当前时间
        time = datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        formatter = {
            "time": time,
            "context": self._core_params.background,
            "question": self._core_params.question,
            "history": self._core_params.history,
        }

        try:
            # 创建一个共用的 Environment
            env = SandboxedEnvironment(
                loader=BaseLoader(),
                autoescape=select_autoescape(),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            # 使用同一个 env 实例来渲染两个模板
            system_input = env.from_string(self._params.system_prompt).render(**formatter)
            user_input = env.from_string(self._params.user_prompt).render(**formatter)
        except Exception as e:
            raise CallError(message=f"用户提示词渲染失败：{e!s}", data={}) from e

        return [
            {"role": "system", "content": system_input},
            {"role": "user", "content": user_input},
        ]

    async def call(self, _slot_data: dict[str, Any]) -> CallResult:
        """运行LLM Call"""
        try:
            message = await self._prepare_message()
            result = ""
            async for chunk in ReasoningLLM().call(task_id=self._core_params.task_id, messages=message):
                result += chunk
        except Exception as e:
            raise CallError(message=f"大模型调用失败：{e!s}", data={}) from e

        return CallResult(
            output={},
            message=result,
            output_schema={},
        )


    async def stream(self, _slot_data: dict[str, Any]) -> AsyncGenerator[str, None]:
        """运行LLM Call的流式输出版本"""
        try:
            message = await self._prepare_message()
            async for chunk in ReasoningLLM().call(
                task_id=self._core_params.task_id,
                messages=message,
                streaming=True,
            ):
                yield chunk
        except Exception as e:
            raise CallError(message=f"大模型流式调用失败：{e!s}", data={}) from e
