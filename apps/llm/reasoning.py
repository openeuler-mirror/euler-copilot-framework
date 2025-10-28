# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问答大模型调用"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk

from apps.common.config import Config
from apps.constants import REASONING_BEGIN_TOKEN, REASONING_END_TOKEN
from apps.llm.token import TokenCalculator
from apps.schemas.config import LLMConfig

logger = logging.getLogger(__name__)


@dataclass
class ReasoningContent:
    """推理内容处理类"""

    content: str = ""
    is_reasoning: bool = False
    reasoning_type: str = ""
    is_first_chunk: bool = True

    def process_first_chunk(self, chunk: ChatCompletionChunk) -> tuple[str, str]:
        """处理第一个chunk"""
        reason = ""
        text = ""

        if (
            hasattr(chunk.choices[0].delta, "reasoning_content")
            # type: ignore[attr-defined]
            and chunk.choices[0].delta.reasoning_content is not None
        ):
            # type: ignore[attr-defined]
            reason = "<think>" + chunk.choices[0].delta.reasoning_content
            self.reasoning_type = "args"
            self.is_reasoning = True
        else:
            for token in REASONING_BEGIN_TOKEN:
                if token == (chunk.choices[0].delta.content or ""):
                    reason = "<think>"
                    self.reasoning_type = "tokens"
                    self.is_reasoning = True
                    break

        self.is_first_chunk = False
        return reason, text

    def process_chunk(self, chunk: ChatCompletionChunk) -> tuple[str, str]:
        """处理普通chunk"""
        reason = ""
        text = ""

        content = chunk.choices[0].delta.content or ""

        if not self.is_reasoning:
            # 非推理模式，直接返回内容作为文本
            text = content
            return reason, text

        if self.reasoning_type == "args":
            if hasattr(
                    chunk.choices[0].delta, "reasoning_content") and chunk.choices[0].delta.reasoning_content is not None:  # type: ignore[attr-defined]
                # 仍在推理中，继续添加推理内容
                # type: ignore[attr-defined]
                reason = chunk.choices[0].delta.reasoning_content or ""
            else:
                # 推理结束，设置标志并添加结束标签
                self.is_reasoning = False
                reason = "</think>"
                # 如果当前内容不是推理内容标签，将其作为文本返回
                text = content.lstrip("</think>")
        elif self.reasoning_type == "tokens":
            for token in REASONING_END_TOKEN:
                if token == content:
                    # 遇到结束标记，推理结束
                    self.is_reasoning = False
                    reason = "</think>"
                    break
            if self.is_reasoning:
                # 仍在推理中，将内容作为推理内容
                reason = content
            else:
                # 推理已结束，将内容作为文本
                text = content

        return reason, text


class ReasoningLLM:
    """调用用于问答的大模型"""

    input_tokens: int = 0
    output_tokens: int = 0

    def __init__(self, llm_config: LLMConfig | None = None) -> None:
        """判断配置文件里用了哪种大模型；初始化大模型客户端"""
        if not llm_config:
            self._config: LLMConfig = Config().get_config().llm
            self._init_client()
        else:
            self._config: LLMConfig = llm_config
            self._init_client()

    def _init_client(self) -> None:
        """初始化OpenAI客户端"""
        if not self._config.key:
            self._client = AsyncOpenAI(
                base_url=self._config.endpoint,
                http_client=httpx.AsyncClient(verify=False)  # 关闭 SSL 验证
            )
            return

        self._client = AsyncOpenAI(
            api_key=self._config.key,
            base_url=self._config.endpoint,
            http_client=httpx.AsyncClient(verify=False)  # 关闭 SSL 验证
        )

    @staticmethod
    def _validate_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """验证消息格式是否正确"""
        if messages[0]["role"] != "system":
            # 添加默认系统消息
            messages.insert(
                0, {"role": "system", "content": "You are a helpful assistant."})

        if messages[-1]["role"] != "user":
            err = f"消息格式错误，最后一个消息必须是用户消息：{messages[-1]}"
            raise ValueError(err)

        return messages

    async def _create_stream(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None,
        temperature: float | None,
        model: str | None = None,
        enable_thinking: bool = False
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """创建流式响应"""
        if model is None:
            model = self._config.model
        if not enable_thinking:
            if len(messages):
                if messages[-1]["role"] == "user":
                    if not messages[-1]["content"].endswith("/no_think"):
                        messages[-1]["content"] += "/no_think"
                else:
                    messages.append(
                        {"role": "user", "content": "/no_think"})
        return await self._client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[]
            max_completion_tokens=max_tokens or self._config.max_tokens,
            temperature=temperature or self._config.temperature,
            stream=True,
            stream_options={"include_usage": True},
            timeout=300,
            extra_body={"enable_thinking": enable_thinking}
        )  # type: ignore[]

    async def call(  # noqa: C901, PLR0912, PLR0913
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        temperature: float | None = None,
        *,
        streaming: bool = True,
        result_only: bool = True,
        model: str | None = None,
        enable_thinking: bool = False
    ) -> AsyncGenerator[str, None]:
        """调用大模型，分为流式和非流式两种"""
        # 检查max_tokens和temperature
        if max_tokens is None:
            max_tokens = self._config.max_tokens
        if temperature is None:
            temperature = self._config.temperature
        if model is None:
            model = self._config.model
        msg_list = self._validate_messages(messages)
        stream = await self._create_stream(msg_list, max_tokens, temperature, model, enable_thinking)
        reasoning = ReasoningContent()
        reasoning_content = ""
        result = ""

        async for chunk in stream:
            # 如果包含统计信息
            if chunk.usage:
                self.input_tokens = chunk.usage.prompt_tokens
                self.output_tokens = chunk.usage.completion_tokens
            # 如果没有Choices
            if not chunk.choices:
                continue

            # 处理chunk
            if reasoning.is_first_chunk:
                reason, text = reasoning.process_first_chunk(chunk)
            else:
                reason, text = reasoning.process_chunk(chunk)

            # 推送消息
            if streaming:
                if reason and not result_only:
                    yield reason
                if text:
                    yield text

            # 整理结果
            reasoning_content += reason
            result += text

        if not streaming:
            if not result_only:
                yield reasoning_content
            yield result

        logger.info("[Reasoning] 推理内容: %s\n\n%s", reasoning_content, result)

        # 更新token统计
        if self.input_tokens == 0 or self.output_tokens == 0:
            self.input_tokens = TokenCalculator().calculate_token_length(
                messages,
            )
            self.output_tokens = TokenCalculator().calculate_token_length(
                [{"role": "assistant", "content": result}],
                pure_text=True,
            )
