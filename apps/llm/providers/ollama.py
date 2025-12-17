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

    def _build_tools_param(self, tools: list[LLMFunctions]) -> list[dict[str, Any]]:
        """构建工具参数"""
        return [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.param_schema,
            },
        } for tool in tools]

    async def _handle_streaming_response(
        self, response: AsyncGenerator[ChatResponse, None],
        messages: list[dict[str, str]],
        tools: list[LLMFunctions] | None,
    ) -> AsyncGenerator[LLMChunk, None]:
        """处理流式响应"""
        last_chunk = None
        async for chunk in response:
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

    async def _handle_non_streaming_response(
        self, response: ChatResponse,
        messages: list[dict[str, str]],
    ) -> AsyncGenerator[LLMChunk, None]:
        """处理非流式响应"""
        if response.message.thinking:
            self.full_thinking = response.message.thinking
        if response.message.content:
            self.full_answer = response.message.content

        # 处理usage数据
        self._process_usage_data(response if response.done else None, messages)

        # 一次性返回完整结果
        yield LLMChunk(
            content=self.full_answer,
            reasoning_content=self.full_thinking,
        )

    def _build_chat_kwargs(
        self, messages: list[dict[str, str]],
        *,
        streaming: bool,
        tools: list[LLMFunctions] | None,
    ) -> dict[str, Any]:
        """构建chat请求参数"""
        chat_kwargs = {
            "messages": messages,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.maxToken,
            },
            "stream": streaming,
            **self.config.extraConfig,
        }

        # 如果modelName存在，则传递该参数
        if self.config.modelName:
            chat_kwargs["model"] = self.config.modelName

        # 如果提供了tools，则传入以启用function-calling模式
        if tools:
            chat_kwargs["tools"] = self._build_tools_param(tools)

        return chat_kwargs

    @override
    async def chat(
        self, messages: list[dict[str, str]],
        tools: list[LLMFunctions] | None = None,
        *, include_thinking: bool = False,
        streaming: bool = True,
    ) -> AsyncGenerator[LLMChunk, None]:
        # 检查能力
        if not self._allow_chat:
            err = "[OllamaProvider] 当前模型不支持Chat"
            _logger.error(err)
            raise RuntimeError(err)

        # 初始化Token计数和累积内容
        self.input_tokens = 0
        self.output_tokens = 0
        self.full_thinking = ""
        self.full_answer = ""

        # 检查消息
        messages = self._validate_messages(messages)

        # 构建chat请求参数
        chat_kwargs = self._build_chat_kwargs(messages, streaming=streaming, tools=tools)

        # 发送请求
        response = await self._client.chat(**chat_kwargs)

        # 根据streaming模式处理响应
        if streaming:
            async for chunk in self._handle_streaming_response(response, messages, tools):
                yield chunk
        else:
            async for chunk in self._handle_non_streaming_response(response, messages):
                yield chunk

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

        # 构建请求参数
        embed_kwargs: dict[str, Any] = {"input": text}

        # 如果modelName存在，则传递该参数
        if self.config.modelName:
            embed_kwargs["model"] = self.config.modelName

        result = await self._client.embed(**embed_kwargs)
        return self._seq_to_list(result.embeddings)
