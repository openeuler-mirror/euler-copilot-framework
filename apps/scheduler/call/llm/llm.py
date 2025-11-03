# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""调用大模型"""

import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any, ClassVar

import pytz
from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field

from apps.llm.reasoning import ReasoningLLM
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.llm.prompt import LLM_CONTEXT_PROMPT, LLM_DEFAULT_PROMPT
from apps.scheduler.call.llm.schema import LLMInput, LLMOutput
from apps.schemas.enum_var import CallOutputType, CallType, LanguageType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)

logger = logging.getLogger(__name__)


class LLM(CoreCall, input_model=LLMInput, output_model=LLMOutput):
    """大模型调用工具"""

    to_user: bool = Field(default=True)
    controlled_output: bool = Field(default=True)
    
    # 输出参数配置
    output_parameters: dict[str, Any] = Field(description="输出参数配置", default={
        "reply": {"type": "string", "description": "大模型的回复内容"},
    })

    # 模型配置
    llmId: str = Field(description="大模型ID", default="")
    
    # 大模型基础参数
    temperature: float = Field(description="大模型温度（随机化程度）", default=0.7)
    enable_temperature: bool = Field(description="是否启用温度参数", default=True)
    enable_context: bool = Field(description="是否启用上下文", default=True)
    enable_thinking: bool = Field(description="是否启用思维链", default=False)
    step_history_size: int = Field(
        description="上下文信息中包含的步骤历史数量", default=3, ge=1, le=10)
    system_prompt: str = Field(
        description="大模型系统提示词", default="You are a helpful assistant.")
    user_prompt: str = Field(description="大模型用户提示词",
                             default=LLM_DEFAULT_PROMPT)
    
    # 新增参数配置
    enable_frequency_penalty: bool = Field(description="是否启用频率惩罚", default=False)
    frequency_penalty: float = Field(description="频率惩罚", default=0.0)
    enable_presence_penalty: bool = Field(description="是否启用内容重复度惩罚", default=False)
    presence_penalty: float = Field(description="内容重复度惩罚", default=0.0)
    enable_min_p: bool = Field(description="是否启用动态过滤阈值", default=False)
    min_p: float = Field(description="动态过滤阈值", default=0.0)
    enable_top_k: bool = Field(description="是否启用Top-K采样", default=False)
    top_k: int = Field(description="Top-K采样值", default=0)
    enable_top_p: bool = Field(description="是否启用Top-P采样", default=False)
    top_p: float = Field(description="Top-P采样值", default=0.9)
    enable_search: bool = Field(description="是否启用联网搜索", default=False)
    enable_json_mode: bool = Field(description="是否启用JSON模式输出", default=False)
    enable_structured_output: bool = Field(description="是否启用结构化输出", default=False)

    i18n_info: ClassVar[dict[str, dict]] = {
        LanguageType.CHINESE: {
            "name": "大模型",
            "type": CallType.DEFAULT,
            "description": "以指定的提示词和上下文信息调用大模型，并获得输出。",
        },
        LanguageType.ENGLISH: {
            "name": "Foundation Model",
            "type": CallType.DEFAULT,
            "description": "Call the foundation model with specified prompt and context, and obtain the output.",
        },
    }

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
        time = datetime.now(tz=pytz.timezone("Asia/Shanghai")
                            ).strftime("%Y-%m-%d %H:%M:%S")
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

    async def _exec(
        self, input_data: dict[str, Any], language: LanguageType = LanguageType.CHINESE
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """运行LLM Call"""
        data = LLMInput(**input_data)
        full_reply = ""  # 用于累积完整回复
        try:
            # 根据llmId获取模型配置
            llm_config = None
            if self.llmId:
                from apps.services.llm import LLMManager
                from apps.llm.adapters import get_provider_from_endpoint
                
                llm_info = await LLMManager.get_llm_by_id(self.llmId)
                if llm_info:
                    from apps.schemas.config import LLMConfig
                    
                    # 获取provider，如果没有则从endpoint推断
                    provider = llm_info.provider or get_provider_from_endpoint(llm_info.openai_base_url)
                    
                    llm_config = LLMConfig(
                        provider=provider,
                        endpoint=llm_info.openai_base_url,
                        key=llm_info.openai_api_key,
                        model=llm_info.model_name,
                        max_tokens=llm_info.max_tokens,
                        temperature=self.temperature if self.enable_temperature else 0.7,
                    )
            
            # 初始化LLM客户端（会自动加载适配器）
            llm = ReasoningLLM(llm_config) if llm_config else ReasoningLLM()
            
            # 准备参数，只传递enable为True的参数
            call_params = {
                "messages": data.message,
                "enable_thinking": self.enable_thinking,
                "temperature": self.temperature if self.enable_temperature else None,
            }
            
            # 添加可选参数（只在enable为True时传递）
            if self.enable_frequency_penalty:
                call_params["frequency_penalty"] = self.frequency_penalty
            if self.enable_presence_penalty:
                call_params["presence_penalty"] = self.presence_penalty
            if self.enable_min_p:
                call_params["min_p"] = self.min_p
            if self.enable_top_k:
                call_params["top_k"] = self.top_k
            if self.enable_top_p:
                call_params["top_p"] = self.top_p
            
            async for chunk in llm.call(**call_params):
                if not chunk:
                    continue
                full_reply += chunk
                yield CallOutputChunk(type=CallOutputType.TEXT, content=chunk)
            self.tokens.input_tokens = llm.input_tokens
            self.tokens.output_tokens = llm.output_tokens
            
            # 最后输出一个DATA chunk，包含完整的输出数据，用于保存到变量池
            yield CallOutputChunk(
                type=CallOutputType.DATA,
                content=LLMOutput(reply=full_reply).model_dump(by_alias=True, exclude_none=True)
            )
        except Exception as e:
            raise CallError(message=f"大模型调用失败：{e!s}", data={}) from e
