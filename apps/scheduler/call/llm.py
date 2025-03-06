"""工具：调用大模型

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any, ClassVar

import pytz
from jinja2 import BaseLoader, select_autoescape
from jinja2.sandbox import SandboxedEnvironment
from pydantic import BaseModel, Field

from apps.constants import LLM_CONTEXT_PROMPT, LLM_DEFAULT_PROMPT
from apps.entities.scheduler import CallError, CallVars
from apps.llm.reasoning import ReasoningLLM
from apps.scheduler.call.core import CoreCall

logger = logging.getLogger("ray")
class LLMNodeOutput(BaseModel):
    """定义LLM工具调用的输出"""

    message: str = Field(description="大模型输出的文字信息")


class LLM(CoreCall, ret_type=LLMNodeOutput):
    """大模型调用工具"""

    name: ClassVar[str] = "大模型"
    description: ClassVar[str] = "以指定的提示词和上下文信息调用大模型，并获得输出。"

    temperature: float = Field(description="大模型温度（随机化程度）", default=0.7)
    enable_context: bool = Field(description="是否启用上下文", default=True)
    step_history_size: int = Field(description="上下文信息中包含的步骤历史数量", default=3)
    system_prompt: str = Field(description="大模型系统提示词", default="")
    user_prompt: str = Field(description="大模型用户提示词", default=LLM_DEFAULT_PROMPT)


    async def _prepare_message(self, syscall_vars: CallVars) -> list[dict[str, Any]]:
        """准备消息"""
        # 创建共享的 Environment 实例
        env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # 上下文信息
        step_history = list(syscall_vars.history.values())[-self.step_history_size:]
        if self.enable_context:
            context_tmpl = env.from_string(LLM_CONTEXT_PROMPT)
            context_prompt = context_tmpl.render(
                summary=syscall_vars.summary,
                history_data=step_history,
            )
        else:
            context_prompt = "无背景信息。"

        # 参数
        time = datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        formatter = {
            "time": time,
            "context": context_prompt,
            "question": syscall_vars.question,
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


    async def init(self, syscall_vars: CallVars, **_kwargs: Any) -> dict[str, Any]:
        """初始化LLM工具"""
        self._message = await self._prepare_message(syscall_vars)
        self._task_id = syscall_vars.task_id
        return {
            "task_id": self._task_id,
            "message": self._message,
        }


    async def exec(self) -> dict[str, Any]:
        """运行LLM Call"""
        try:
            result = ""
            async for chunk in ReasoningLLM().call(task_id=self._task_id, messages=self._message):
                result += chunk
        except Exception as e:
            raise CallError(message=f"大模型调用失败：{e!s}", data={}) from e

        result = result.strip().strip("\n")
        return LLMNodeOutput(message=result).model_dump(exclude_none=True, by_alias=True)


    async def stream(self) -> AsyncGenerator[str, None]:
        """流式输出"""
        try:
            async for chunk in ReasoningLLM().call(task_id=self._task_id, messages=self._message):
                yield chunk
        except Exception as e:
            raise CallError(message=f"大模型流式输出失败：{e!s}", data={}) from e
