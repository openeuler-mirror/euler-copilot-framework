# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型提供商：OpenAI"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, cast

import httpx
from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessage,
    ChatCompletionMessageParam,
)
from typing_extensions import override

from apps.llm.token import token_calculator
from apps.models import LLMType
from apps.schemas.llm import LLMChunk, LLMFunctions, LLMToolCall

from .base import BaseProvider

_logger = logging.getLogger(__name__)

class OpenAIProvider(BaseProvider):
    """OpenAI大模型客户端"""

    _client: AsyncOpenAI
    _http_client: httpx.AsyncClient
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
        self._http_client = httpx.AsyncClient(verify=False)  # noqa: S501
        if not self.config.apiKey:
            self._client = AsyncOpenAI(
                base_url=self.config.baseUrl,
                timeout=self._timeout,
                http_client=self._http_client,
            )
        else:
            self._client = AsyncOpenAI(
                base_url=self.config.baseUrl,
                api_key=self.config.apiKey,
                timeout=self._timeout,
                http_client=self._http_client,
            )

    def _parse_tool_calls(self, message: ChatCompletionMessage) -> list[LLMToolCall]:
        """解析工具调用并转换为LLMToolCall列表"""
        tool_calls_list: list[LLMToolCall] = []

        if not hasattr(message, "tool_calls") or not message.tool_calls:
            return tool_calls_list

        for tool_call in message.tool_calls:
            if tool_call.type == "function" and hasattr(tool_call, "function"):
                func = tool_call.function
                try:
                    # 解析JSON字符串为字典
                    arguments = json.loads(func.arguments) if isinstance(func.arguments, str) else func.arguments
                    tool_calls_list.append(LLMToolCall(
                        id=tool_call.id,
                        name=func.name,
                        arguments=arguments,
                    ))
                except (json.JSONDecodeError, TypeError):
                    # 如果JSON解析失败，忽略这个工具调用
                    _logger.warning(
                        "[OpenAIProvider] 工具调用参数解析失败: tool_call_id=%s, name=%s",
                        tool_call.id,
                        func.name,
                    )
                    continue

        return tool_calls_list

    def _handle_usage_chunk(self, chunk: ChatCompletionChunk | None, messages: list[dict[str, str]]) -> None:
        """处理包含usage信息的chunk"""
        if chunk and getattr(chunk, "usage", None):
            try:
                # 使用服务端统计的token计数
                usage = chunk.usage
                if usage and hasattr(usage, "prompt_tokens") and hasattr(usage, "completion_tokens"):
                    self.input_tokens += usage.prompt_tokens
                    self.output_tokens += usage.completion_tokens
            except Exception:  # noqa: BLE001
                # 忽略异常，保持已有的token统计逻辑
                _logger.warning("[OpenAIProvider] 推理框架未返回使用数据，使用本地估算逻辑")

        # 如果没有从服务端获取到token计数，使用本地估算
        if not self.input_tokens or not self.output_tokens:
            self.input_tokens += token_calculator.calculate_token_length(messages)
            self.output_tokens += token_calculator.calculate_token_length([{
                "role": "assistant",
                "content": "<think>" + self.full_thinking + "</think>" + self.full_answer,
            }])

    def _handle_usage_response(self, response: ChatCompletion, messages: list[dict[str, str]]) -> None:
        """处理非流式响应的usage信息"""
        if hasattr(response, "usage") and response.usage:
            self.input_tokens += response.usage.prompt_tokens
            self.output_tokens += response.usage.completion_tokens
        else:
            # 回退到本地估算
            self.input_tokens += token_calculator.calculate_token_length(messages)
            self.output_tokens += token_calculator.calculate_token_length([{
                "role": "assistant",
                "content": "<think>" + self.full_thinking + "</think>" + self.full_answer,
            }])

    def _build_request_kwargs(
        self,
        messages: list[dict[str, str]],
        *,
        streaming: bool,
        temperature: float = 0.7,
    ) -> dict:
        """构建请求参数"""
        request_kwargs = {
            "messages": self._convert_messages(messages),
            "max_tokens": self.config.maxToken,
            "temperature": temperature,
            "stream": streaming,
            **self.config.extraConfig,
        }

        # 如果modelName存在，则传递该参数
        if self.config.modelName:
            request_kwargs["model"] = self.config.modelName

        # 流式模式下添加usage统计选项
        if streaming:
            request_kwargs["stream_options"] = {"include_usage": True}

        return request_kwargs

    def _add_tools_to_request(
        self,
        request_kwargs: dict,
        tools: list[LLMFunctions],
    ) -> None:
        """将工具添加到请求参数中"""
        functions = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.param_schema,
                },
            }
            for tool in tools
        ]
        request_kwargs["tools"] = functions

    async def _process_streaming_chunk(
        self,
        chunk: ChatCompletionChunk,
        *,
        include_thinking: bool,
    ) -> AsyncGenerator[LLMChunk, None]:
        """处理单个流式响应chunk"""
        if not hasattr(chunk, "choices") or not chunk.choices:
            return

        delta = chunk.choices[0].delta

        # 处理reasoning_content
        if (
            hasattr(delta, "reasoning_content") and
            getattr(delta, "reasoning_content", None) and
            include_thinking
        ):
            reasoning_content = getattr(delta, "reasoning_content", "")
            self.full_thinking += reasoning_content
            yield LLMChunk(reasoning_content=reasoning_content)

        # 处理content
        if hasattr(delta, "content") and delta.content:
            self.full_answer += delta.content
            yield LLMChunk(content=delta.content)

    async def _handle_streaming_response(
        self,
        request_kwargs: dict,
        messages: list[dict[str, str]],
        *,
        include_thinking: bool,
    ) -> AsyncGenerator[LLMChunk, None]:
        """处理流式响应"""
        stream: AsyncStream[ChatCompletionChunk] = await self._client.chat.completions.create(**request_kwargs)
        last_chunk = None

        async for chunk in stream:
            last_chunk = chunk
            async for llm_chunk in self._process_streaming_chunk(
                chunk,
                include_thinking=include_thinking,
            ):
                yield llm_chunk

        # 处理最后一个Chunk的usage
        self._handle_usage_chunk(last_chunk, messages)

    async def _handle_non_streaming_response(
        self,
        request_kwargs: dict,
        messages: list[dict[str, str]],
        tools: list[LLMFunctions] | None,
        *,
        include_thinking: bool,
    ) -> AsyncGenerator[LLMChunk, None]:
        """处理非流式响应"""
        response: ChatCompletion = await self._client.chat.completions.create(**request_kwargs)
        tool_calls_list: list[LLMToolCall] = []

        if response.choices:
            message = response.choices[0].message

            # 处理reasoning_content
            if (
                hasattr(message, "reasoning_content") and
                getattr(message, "reasoning_content", None) and
                include_thinking
            ):
                self.full_thinking = getattr(message, "reasoning_content", "")

            # 处理content
            if hasattr(message, "content") and message.content:
                self.full_answer = message.content

            # 处理工具调用
            if tools:
                tool_calls_list = self._parse_tool_calls(message)

        # 处理usage数据
        self._handle_usage_response(response, messages)

        # 一次性返回完整结果
        yield LLMChunk(
            content=self.full_answer,
            reasoning_content=self.full_thinking,
            tool_call=tool_calls_list if tool_calls_list else None,
        )

    @override
    async def chat(
        self, messages: list[dict[str, str]],
        tools: list[LLMFunctions] | None = None,
        *, include_thinking: bool = False,
        streaming: bool = True,
        temperature: float = 0.7,
    ) -> AsyncGenerator[LLMChunk, None]:
        """聊天"""
        # 检查能力
        if not self._allow_chat:
            err = "[OpenAIProvider] 当前模型不支持Chat"
            _logger.error(err)
            raise RuntimeError(err)

        # 初始化Token计数和累积内容
        if not hasattr(self, "input_tokens"):
            self.input_tokens = 0
        if not hasattr(self, "output_tokens"):
            self.output_tokens = 0
        self.full_thinking = ""
        self.full_answer = ""

        # 检查消息
        messages = self._validate_messages(messages)

        # 构建请求参数
        request_kwargs = self._build_request_kwargs(messages, streaming=streaming, temperature=temperature)

        # 如果提供了tools，则启用function-calling模式
        if tools:
            self._add_tools_to_request(request_kwargs, tools)

        # 根据模式选择处理方式
        if streaming:
            async for chunk in self._handle_streaming_response(
                request_kwargs,
                messages,
                include_thinking=include_thinking,
            ):
                yield chunk
        else:
            async for chunk in self._handle_non_streaming_response(
                request_kwargs,
                messages,
                tools,
                include_thinking=include_thinking,
            ):
                yield chunk

    @override
    async def embedding(self, text: list[str]) -> list[list[float]]:
        if not self._allow_embedding:
            err = "[OpenAIProvider] 当前模型不支持Embedding"
            _logger.error(err)
            raise RuntimeError(err)

        # 构建请求参数
        embedding_kwargs: dict[str, Any] = {"input": text}

        # 如果modelName存在，则传递该参数
        if self.config.modelName:
            embedding_kwargs["model"] = self.config.modelName

        # 使用 AsyncOpenAI 客户端的 embedding 功能
        response = await self._client.embeddings.create(**embedding_kwargs)
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
