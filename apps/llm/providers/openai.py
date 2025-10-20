# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型提供商：OpenAI"""

import logging
from collections.abc import AsyncGenerator
from typing import cast

from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import (
    ChatCompletionChunk,
    ChatCompletionMessageParam,
)
from typing_extensions import override

from apps.llm.token import token_calculator
from apps.models import LLMType
from apps.schemas.llm import LLMChunk, LLMFunctions

from .base import BaseProvider

_logger = logging.getLogger(__name__)

class OpenAIProvider(BaseProvider):
    """OpenAI大模型客户端"""

    _client: AsyncOpenAI
    input_tokens: int
    output_tokens: int
    _allow_chat: bool
    _allow_function: bool
    _allow_embedding: bool

    @override
    def _check_type(self) -> None:
        """检查模型能力"""
        if LLMType.VISION in self.config.llmType:
            err = "[OpenAIProvider] 当前暂不支持视觉模型"
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
        """初始化模型API客户端"""
        if not self.config.apiKey:
            self._client = AsyncOpenAI(
                base_url=self.config.baseUrl,
                timeout=self._timeout,
            )
        else:
            self._client = AsyncOpenAI(
                base_url=self.config.baseUrl,
                api_key=self.config.apiKey,
                timeout=self._timeout,
            )

    def _handle_usage_chunk(self, chunk: ChatCompletionChunk | None, messages: list[dict[str, str]]) -> None:
        """处理包含usage信息的chunk"""
        if chunk and getattr(chunk, "usage", None):
            try:
                # 使用服务端统计的token计数
                usage = chunk.usage
                if usage and hasattr(usage, "prompt_tokens") and hasattr(usage, "completion_tokens"):
                    self.input_tokens = usage.prompt_tokens
                    self.output_tokens = usage.completion_tokens
            except Exception:  # noqa: BLE001
                # 忽略异常，保持已有的token统计逻辑
                _logger.warning("[OpenAIProvider] 推理框架未返回使用数据，使用本地估算逻辑")

        # 如果没有从服务端获取到token计数，使用本地估算
        if not self.input_tokens or not self.output_tokens:
            self.input_tokens = token_calculator.calculate_token_length(messages)
            self.output_tokens = token_calculator.calculate_token_length([{
                "role": "assistant",
                "content": "<think>" + self.full_thinking + "</think>" + self.full_answer,
            }])

    @override
    async def chat(  # noqa: C901
        self, messages: list[dict[str, str]],
        *, include_thinking: bool = False,
        tools: list[LLMFunctions] | None = None,
    ) -> AsyncGenerator[LLMChunk, None]:
        """聊天"""
        # 检查能力
        if not self._allow_chat:
            err = "[OpenAIProvider] 当前模型不支持Chat"
            _logger.error(err)
            raise RuntimeError(err)

        # 初始化Token计数
        self.input_tokens = 0
        self.output_tokens = 0

        # 检查消息
        messages = self._validate_messages(messages)

        request_kwargs = {
            "model": self.config.modelName,
            "messages": self._convert_messages(messages),
            "max_tokens": self.config.maxToken,
            "temperature": self.config.temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
            **self.config.extraConfig,
        }

        # 如果提供了tools，则启用function-calling模式
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
            request_kwargs["tools"] = functions

        stream: AsyncStream[ChatCompletionChunk] = await self._client.chat.completions.create(**request_kwargs)
        # 流式返回响应
        last_chunk = None
        async for chunk in stream:
            last_chunk = chunk
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                if (
                    hasattr(delta, "reasoning_content") and
                    getattr(delta, "reasoning_content", None) and
                    include_thinking
                ):
                    reasoning_content = getattr(delta, "reasoning_content", "")
                    self.full_thinking += reasoning_content
                    yield LLMChunk(reasoning_content=reasoning_content)

                if (
                    hasattr(chunk.choices[0].delta, "content") and
                    chunk.choices[0].delta.content
                ):
                    self.full_answer += chunk.choices[0].delta.content
                    yield LLMChunk(content=chunk.choices[0].delta.content)

                # 在chat中统一处理工具调用分块（当提供了tools时）
                if tools and hasattr(delta, "tool_calls") and delta.tool_calls:
                    tool_call_dict = {}
                    for tool_call in delta.tool_calls:
                        if hasattr(tool_call, "function") and tool_call.function:
                            tool_call_dict.update({
                                tool_call.function.name: tool_call.function.arguments,
                            })
                    if tool_call_dict:
                        yield LLMChunk(tool_call=tool_call_dict)

        # 处理最后一个Chunk的usage（仅在最后一个chunk会出现）
        self._handle_usage_chunk(last_chunk, messages)

    @override
    async def embedding(self, text: list[str]) -> list[list[float]]:
        if not self._allow_embedding:
            err = "[OpenAIProvider] 当前模型不支持Embedding"
            _logger.error(err)
            raise RuntimeError(err)

        # 使用 AsyncOpenAI 客户端的 embedding 功能
        response = await self._client.embeddings.create(
            input=text,
            model=self.config.modelName,
        )
        return [data.embedding for data in response.data]


    def _convert_messages(self, messages: list[dict[str, str]]) -> list[ChatCompletionMessageParam]:
        """确保消息格式符合OpenAI API要求，特别是tool消息需要tool_call_id字段"""
        result: list[dict[str, str]] = []
        for msg in messages:
            role = msg.get("role", "user")

            # 验证角色的有效性
            if role not in ("system", "user", "assistant", "tool"):
                err = f"[OpenAIProvider] 未知角色: {role}"
                _logger.error(err)
                raise ValueError(err)

            # 对于tool角色，确保有tool_call_id字段
            if role == "tool" and "tool_call_id" not in msg:
                result.append({**msg, "tool_call_id": ""})
            else:
                result.append(msg)

        # 使用cast告诉类型检查器这是ChatCompletionMessageParam类型
        # OpenAI库在运行时接受dict格式，无需显式构造TypedDict对象
        return cast("list[ChatCompletionMessageParam]", result)
