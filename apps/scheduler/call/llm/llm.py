"""
工具：调用大模型

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

import pytz
from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field

from apps.entities.enum_var import CallOutputType
from apps.entities.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)
from apps.llm.reasoning import ReasoningLLM
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.llm.schema import LLM_CONTEXT_PROMPT, LLM_DEFAULT_PROMPT, LLMInput, LLMOutput

logger = logging.getLogger(__name__)


class LLM(CoreCall, input_model=LLMInput, output_model=LLMOutput):
    """大模型调用工具"""

    to_user: bool = Field(default=True)

    # 大模型参数
    temperature: float = Field(description="大模型温度（随机化程度）", default=0.7)
    enable_context: bool = Field(description="是否启用上下文", default=True)
    step_history_size: int = Field(description="上下文信息中包含的步骤历史数量", default=3, ge=1, le=10)
    system_prompt: str = Field(description="大模型系统提示词", default="You are a helpful assistant.")
    user_prompt: str = Field(description="大模型用户提示词", default=LLM_DEFAULT_PROMPT)


    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(name="大模型", description="以指定的提示词和上下文信息调用大模型，并获得输出。")


    async def _prepare_message(self, call_vars: CallVars) -> list[dict[str, Any]]:
        """准备消息"""
        # 创建共享的 Environment 实例
        env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # 上下文信息
        step_history = []
        for ids in call_vars.history_order[-self.step_history_size:]:
            step_history += [call_vars.history[ids]]

        if self.enable_context:
            context_tmpl = env.from_string(LLM_CONTEXT_PROMPT)
            context_prompt = context_tmpl.render(
                summary=call_vars.summary,
                history_data=step_history,
            )
        else:
            context_prompt = "无背景信息。"

        # 参数
        time = datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        formatter = {
            "time": time,
            "context": context_prompt,
            "question": call_vars.question,
        }

        try:
            # 准备系统提示词
            system_tmpl = env.from_string(self.system_prompt)
            system_input = system_tmpl.render(**formatter)

            # 准备用户提示词
            user_tmpl = env.from_string(self.user_prompt)
            user_input = user_tmpl.render(**formatter)
        except Exception as e:
            raise CallError(message=f"用户提示词渲染失败：{e!s}", data={}) from e

        return [
            {"role": "system", "content": system_input},
            {"role": "user", "content": user_input},
        ]


    async def _init(self, call_vars: CallVars) -> LLMInput:
        """初始化LLM工具"""
        return LLMInput(
            message=await self._prepare_message(call_vars),
        )


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """运行LLM Call"""
        data = LLMInput(**input_data)
        try:
            llm = ReasoningLLM()
            async for chunk in llm.call(messages=data.message):
                if not chunk:
                    continue
                yield CallOutputChunk(type=CallOutputType.TEXT, content=chunk)
            self.tokens.input_tokens = llm.input_tokens
            self.tokens.output_tokens = llm.output_tokens
        except Exception as e:
            raise CallError(message=f"大模型调用失败：{e!s}", data={}) from e
