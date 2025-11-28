# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""调用大模型"""

import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

import pytz
from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field

from apps.constants import APP_DEFAULT_HISTORY_LEN
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

logger = logging.getLogger(__name__)


def _tojson_filter(value: Any, *, ensure_ascii: bool = True, indent: int | None = None) -> str:
    """自定义JSON过滤器，支持ensure_ascii和indent参数"""
    return json.dumps(value, ensure_ascii=ensure_ascii, indent=indent)


class LLM(CoreCall, input_model=LLMInput, output_model=LLMOutput):
    """大模型调用工具"""

    to_user: bool = Field(default=True)
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

    def _build_step_memory_messages(
        self,
        call_vars: CallVars,
        env: SandboxedEnvironment,
    ) -> list[dict[str, Any]]:
        """
        构建步骤记忆消息

        将 step_history 格式化为标准的 OpenAI messages 格式
        """
        if self.step_history_size <= 0:
            return []

        step_history = [call_vars.step_data[ids] for ids in call_vars.step_order[-self.step_history_size:]]

        step_memory_prompt = self._load_prompt("llm_step_memory")
        step_memory_tmpl = env.from_string(step_memory_prompt)

        messages: list[dict[str, Any]] = []
        for index, step in enumerate(step_history, start=1):
            user_content = step_memory_tmpl.render(
                role="user",
                step_index=index,
                step_goal=step.extraData.get("goal", "未指定目标"),
                step_name=step.stepName,
                input_data=step.inputData,
            )
            messages.append({"role": "user", "content": user_content})

            assistant_content = step_memory_tmpl.render(
                role="assistant",
                step_index=index,
                step_status=step.stepStatus.value,
                output_data=step.outputData,
            )
            messages.append({"role": "assistant", "content": assistant_content})

        return messages

    def _get_history_messages(self, call_vars: CallVars) -> list[dict[str, Any]]:
        """获取历史对话消息"""
        history_len = self.history_length
        if history_len is None and call_vars.app_metadata is not None:
            history_len = call_vars.app_metadata.history_len

        if history_len is None:
            history_len = APP_DEFAULT_HISTORY_LEN

        if history_len <= 0:
            return []

        conversation = self._sys_vars.background.conversation
        return conversation[-history_len * 2:]

    def _render_prompts(
        self,
        env: SandboxedEnvironment,
        formatter: dict[str, Any],
    ) -> tuple[str, str]:
        """渲染系统提示词和用户提示词"""
        try:
            system_tmpl = env.from_string(self.system_prompt)
            system_input = system_tmpl.render(**formatter)

            user_prompt = self._load_prompt("llm") if self.user_prompt is None else self.user_prompt
            user_tmpl = env.from_string(user_prompt)
            user_input = user_tmpl.render(**formatter)
        except Exception as e:
            raise CallError(message=f"用户提示词渲染失败:{e!s}", data={}) from e
        else:
            return system_input, user_input

    async def _prepare_message(self, call_vars: CallVars) -> list[dict[str, Any]]:
        """准备消息"""
        env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            extensions=["jinja2.ext.loopcontrols"],
        )
        env.filters["tojson"] = _tojson_filter

        step_memory_messages = self._build_step_memory_messages(call_vars, env)
        history_messages = self._get_history_messages(call_vars)

        time = datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        formatter = {
            "time": time,
            "question": call_vars.question,
            "history": self._sys_vars.background.conversation,
        }

        system_input, user_input = self._render_prompts(env, formatter)

        messages = [{"role": "system", "content": system_input}]
        messages.extend(step_memory_messages)
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
