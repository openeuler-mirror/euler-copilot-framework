# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问答大模型调用"""

import logging
from collections.abc import AsyncGenerator

from apps.models import LLMData, LLMProvider
from apps.schemas.llm import LLMChunk, LLMFunctions

from .providers import (
    BaseProvider,
    OllamaProvider,
    OpenAIProvider,
)

_logger = logging.getLogger(__name__)
_CLASS_DICT: dict[LLMProvider, type[BaseProvider]] = {
    LLMProvider.OLLAMA: OllamaProvider,
    LLMProvider.OPENAI: OpenAIProvider,
}


class LLM:
    """调用用于问答的大模型"""

    def __init__(self, llm_config: LLMData | None) -> None:
        """判断配置文件里用了哪种大模型；初始化大模型客户端"""
        if not llm_config:
            err = "[ReasoningLLM] 未设置问答LLM"
            _logger.error(err)
            raise RuntimeError(err)

        if llm_config.provider not in _CLASS_DICT:
            err = "[ReasoningLLM] 未支持的问答LLM类型: %s", llm_config.provider
            _logger.error(err)
            raise RuntimeError(err)

        self._provider = _CLASS_DICT[llm_config.provider](llm_config)

    async def call(
        self,
        messages: list[dict[str, str]],
        *,
        include_thinking: bool = True,
        streaming: bool = True,
        tools: list[LLMFunctions] | None = None,
    ) -> AsyncGenerator[LLMChunk, None]:
        """调用大模型，分为流式和非流式两种"""
        if streaming:
            async for chunk in await self._provider.chat(
                messages,
                include_thinking=include_thinking,
                tools=tools,
            ):
                yield chunk
        else:
            # 非流式模式下，需要收集所有内容
            async for _ in await self._provider.chat(
                messages,
                include_thinking=include_thinking,
                tools=tools,
            ):
                continue
            # 直接yield最终结果
            yield LLMChunk(
                content=self._provider.full_answer,
                reasoning_content=self._provider.full_thinking,
            )

    @property
    def input_tokens(self) -> int:
        """获取输入token数"""
        return self._provider.input_tokens

    @property
    def output_tokens(self) -> int:
        """获取输出token数"""
        return self._provider.output_tokens

    @property
    def config(self) -> LLMData:
        """获取大模型配置"""
        return self._provider.config
