# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""调用大模型"""

import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pytz
from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field

from apps.models import LanguageType
from apps.scheduler.call.core import CoreCall
from apps.schemas.enum_var import CallOutputType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)

from .schema import LLMInput, LLMOutput

if TYPE_CHECKING:
    from apps.models.task import ExecutorHistory

logger = logging.getLogger(__name__)


class LLM(CoreCall, input_model=LLMInput, output_model=LLMOutput):
    """大模型调用工具"""

    to_user: bool = Field(default=True)

    # 大模型参数
    temperature: float = Field(description="大模型温度（随机化程度）", default=0.7)
    step_history_size: int = Field(description="上下文信息中包含的步骤历史数量", default=3, ge=0, le=10)
    history_length: int | None = Field(description="历史对话记录数量", default=None, ge=0)
    system_prompt: str = Field(description="大模型系统提示词", default="You are a helpful assistant.")
    user_prompt: str | None = Field(description="大模型用户提示词", default=None)


    @classmethod
    def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
        """返回Call的名称和描述"""
        i18n_info = {
            LanguageType.CHINESE: CallInfo(
                name="大模型",
                description="以指定的提示词和上下文信息调用大模型，并获得输出。",
            ),
            LanguageType.ENGLISH: CallInfo(
                name="LLM",
                description="Call an LLM with specified prompts and context information and get output.",
            ),
        }
        return i18n_info[language]


    async def _prepare_message(self, call_vars: CallVars) -> list[dict[str, Any]]:
        """准备消息"""
        # 创建共享的 Environment 实例
        env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            extensions=["jinja2.ext.loopcontrols"],
        )

        # 上下文信息
        step_history: list[ExecutorHistory] = []
        for ids in call_vars.step_order[-self.step_history_size:]:
            step_history += [call_vars.step_data[ids]]

        if self.step_history_size > 0:
            context_tmpl = env.from_string(LLM_CONTEXT_PROMPT[self._sys_vars.language])
            context_prompt = context_tmpl.render(
                reasoning=call_vars.thinking,
                context_data=step_history,
            )
        else:
            context_prompt = "无背景信息。"

        history_messages = []
        history_len = self.history_length
        if history_len is None and call_vars.app_metadata is not None:
            history_len = call_vars.app_metadata.history_len

        if history_len is not None and history_len > 0:
            conversation = self._sys_vars.background.conversation
            # 每对消息包含 2 条记录（user + assistant）
            history_messages = conversation[-history_len * 2:]

        # 参数
        time = datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        formatter = {
            "time": time,
            "context": context_prompt,
            "question": call_vars.question,
            "history": self._sys_vars.background.conversation,
        }

        try:
            # 准备系统提示词
            system_tmpl = env.from_string(self.system_prompt)
            system_input = system_tmpl.render(**formatter)

            # 准备用户提示词
            user_prompt = self.user_prompt if self.user_prompt is not None else self._load_prompt("llm")
            user_tmpl = env.from_string(user_prompt)
            user_input = user_tmpl.render(**formatter)
        except Exception as e:
            raise CallError(message=f"用户提示词渲染失败：{e!s}", data={}) from e

        # 构建消息列表，将历史消息放在前面
        messages = [{"role": "system", "content": system_input}]
        messages.extend(history_messages)
        messages.append({"role": "user", "content": user_input})

        return messages


    async def _init(self, call_vars: CallVars) -> LLMInput:
        """初始化LLM工具"""
        return LLMInput(
            message=await self._prepare_message(call_vars),
        )


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """运行LLM Call"""
        data = LLMInput(**input_data)
        try:
            async for chunk in self._llm(messages=data.message, streaming=True):
                if not chunk:
                    continue
                yield CallOutputChunk(type=CallOutputType.TEXT, content=chunk)
        except Exception as e:
            raise CallError(message=f"大模型调用失败：{e!s}", data={}) from e
