# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Ollama大模型服务"""

import logging
from collections.abc import AsyncGenerator, Sequence
from typing import Any

from ollama import AsyncClient, ChatResponse
from typing_extensions import override

from apps.llm.token import token_calculator
from apps.models import LLMType
from apps.schemas.llm import LLMChunk, LLMFunctions

from .base import BaseProvider

_logger = logging.getLogger(__name__)

class OllamaProvider(BaseProvider):
    """Ollama大模型服务"""

    @override
    def _check_type(self) -> None:
        """检查大模型类型"""
        if LLMType.VISION in self.config.llmType:
            err = "[OllamaProvider] 当前暂不支持视觉模型"
            _logger.error(err)
            raise RuntimeError(err)

        if LLMType.CHAT not in self.config.llmType:
            self._allow_chat = False
        else:
            self._allow_chat = True
        if LLMType.FUNCTION not in self.config.llmType:
            self._allow_function = False
        else:
            self._allow_function = True
        if LLMType.EMBEDDING not in self.config.llmType:
            self._allow_embedding = False
        else:
            self._allow_embedding = True

    @override
    def _init_client(self) -> None:
        """初始化客户端"""
        if not self.config.apiKey:
            self._client = AsyncClient(
                host=self.config.baseUrl,
                timeout=self._timeout,
                verify=False,
            )
        else:
            self._client = AsyncClient(
                host=self.config.baseUrl,
                headers={
                    "Authorization": f"Bearer {self.config.apiKey}",
                },
                timeout=self._timeout,
                verify=False,
            )

    def _process_usage_data(self, last_chunk: ChatResponse | None, messages: list[dict[str, str]]) -> None:
        """处理最后一个chunk的usage数据"""
        if last_chunk and last_chunk.done:
            self.input_tokens = last_chunk.prompt_eval_count or 0
            self.output_tokens = last_chunk.eval_count or 0
            _logger.info(
                "[OllamaProvider] 使用Ollama统计数据: input_tokens=%s, output_tokens=%s",
                self.input_tokens, self.output_tokens,
            )
        else:
            # 如果无法获取统计数据，回退到本地估算
            _logger.warning("[OllamaProvider] 无法获取Ollama统计数据，使用本地估算逻辑")
            self.input_tokens = token_calculator.calculate_token_length(messages)
            self.output_tokens = token_calculator.calculate_token_length([{
                "role": "assistant",
                "content": "<think>" + self.full_thinking + "</think>" + self.full_answer,
            }])

    @override
    async def chat(
        self, messages: list[dict[str, str]],
        *, include_thinking: bool = False,
        tools: list[LLMFunctions] | None = None,
    ) -> AsyncGenerator[LLMChunk, None]:
        # 检查能力
        if not self._allow_chat:
            err = "[OllamaProvider] 当前模型不支持Chat"
            _logger.error(err)
            raise RuntimeError(err)

        # 初始化Token计数
        self.input_tokens = 0
        self.output_tokens = 0

        # 检查消息
        messages = self._validate_messages(messages)

        # 流式返回响应
        last_chunk = None
        chat_kwargs = {
            "model": self.config.modelName,
            "messages": messages,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.maxToken,
            },
            "stream": True,
            **self.config.extraConfig,
        }

        # 如果提供了tools，则传入以启用function-calling模式
        if tools:
            functions = []
            for tool in tools:
                functions += [{
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.param_schema,
                    },
                }]
            chat_kwargs["tools"] = functions

        async for chunk in await self._client.chat(**chat_kwargs):
            last_chunk = chunk
            if chunk.message.thinking:
                self.full_thinking += chunk.message.thinking
                yield LLMChunk(reasoning_content=chunk.message.thinking)
            if chunk.message.content:
                self.full_answer += chunk.message.content
                yield LLMChunk(content=chunk.message.content)

            # 在chat中统一处理工具调用分块（当提供了tools时）
            if tools and chunk.message.tool_calls:
                tool_call_dict = {}
                for tool_call in chunk.message.tool_calls:
                    tool_call_dict.update({
                        tool_call.function.name: tool_call.function.arguments,
                    })
                if tool_call_dict:
                    yield LLMChunk(tool_call=tool_call_dict)

        # 使用最后一个chunk的usage数据
        self._process_usage_data(last_chunk, messages)

    def _seq_to_list(self, seq: Sequence[Any]) -> list[Any]:
        """将Sequence转换为list"""
        result = []
        for item in seq:
            if isinstance(item, (list, tuple, range)):
                result.extend(self._seq_to_list(item))
            else:
                result.append(item)
        return result

    @override
    async def embedding(self, text: list[str]) -> list[list[float]]:
        """文本向量化"""
        if not self._allow_embedding:
            err = "[OllamaProvider] 当前模型不支持Embedding"
            _logger.error(err)
            raise RuntimeError(err)

        result = await self._client.embed(
            model=self.config.modelName,
            input=text,
        )
        return self._seq_to_list(result.embeddings)


