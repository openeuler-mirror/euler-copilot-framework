# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问答大模型调用"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk

from apps.common.config import Config
from apps.constants import REASONING_BEGIN_TOKEN, REASONING_END_TOKEN
from apps.llm.token import TokenCalculator
from apps.llm.adapters import AdapterFactory, get_provider_from_endpoint
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
        content = chunk.choices[0].delta.content or ""

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
            # 检查内容是否包含思维链开始标记
            for token in REASONING_BEGIN_TOKEN:
                if token in content:
                    self.reasoning_type = "tokens"
                    self.is_reasoning = True
                    # 分离思维链内容和普通文本
                    if content.startswith(token):
                        # 内容以<think>开始
                        reason_content = content[len(token):]
                        reason = "<think>" + reason_content
                    else:
                        # <think>在内容中间，分离前后部分
                        parts = content.split(token, 1)
                        text = parts[0]  # <think>之前的内容作为普通文本
                        reason = "<think>" + \
                            (parts[1] if len(parts) > 1 else "")
                    break

            # 如果没有检测到思维链标记，将内容作为普通文本
            if not self.is_reasoning:
                text = content

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
            # 检查内容是否包含结束标记
            end_token_found = False
            for token in REASONING_END_TOKEN:
                if token in content:
                    # 遇到结束标记，推理结束
                    self.is_reasoning = False
                    end_token_found = True
                    # 分离思维链内容和普通文本
                    if content.endswith(token):
                        # 内容以</think>结束
                        reason_content = content[:-len(token)]
                        reason = reason_content + "</think>"
                    else:
                        # </think>在内容中间，分离前后部分
                        parts = content.split(token, 1)
                        reason = parts[0] + "</think>"
                        # </think>之后的内容作为普通文本
                        text = parts[1] if len(parts) > 1 else ""
                    break

            if not end_token_found:
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

        # 初始化适配器
        # 优先使用配置中的provider，如果没有则从endpoint推断
        if hasattr(self._config, 'provider') and self._config.provider:
            self._provider = self._config.provider
        else:
            self._provider = get_provider_from_endpoint(self._config.endpoint)
        self._adapter = AdapterFactory.create_adapter(
            self._provider, self._config.model)

    def _init_client(self) -> None:
        """初始化OpenAI客户端"""
        if not self._config.api_key:
            self._client = AsyncOpenAI(
                base_url=self._config.endpoint,
            )
            return

        self._client = AsyncOpenAI(
            api_key=self._config.key,
            base_url=self._config.endpoint,
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
        enable_thinking: bool = False,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        min_p: float | None = None,
        top_k: int | None = None,
        top_p: float | None = None,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """创建流式响应"""
        if model is None:
            model = self._config.model

        # 处理思维链控制
        messages_copy = [msg.copy() for msg in messages]

        # 如果不支持原生thinking，使用prompt方式控制
        if self._adapter.should_use_prompt_thinking(enable_thinking):
            # 启用思维链但模型不支持原生thinking，不添加/no_think
            pass
        elif not enable_thinking:
            # 不启用思维链，添加/no_think指令
            if len(messages_copy):
                if messages_copy[-1]["role"] == "user":
                    if not messages_copy[-1]["content"].endswith("/no_think"):
                        messages_copy[-1]["content"] += "/no_think"
                else:
                    messages_copy.append(
                        {"role": "user", "content": "/no_think"})

        # 构建基础参数
        base_params = {
            "model": model,
            "messages": messages_copy,  # type: ignore[]
            "max_completion_tokens": max_tokens or self._config.max_tokens,
            "temperature": temperature or self._config.temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
            "timeout": 300,
        }

        # 初始化 extra_body
        extra_body_params = {}

        # enable_thinking 始终放在 extra_body 中
        extra_body_params["enable_thinking"] = enable_thinking

        # 添加扩展参数到 extra_body（这些参数不被标准 OpenAI SDK 支持）
        if frequency_penalty is not None:
            extra_body_params["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            extra_body_params["presence_penalty"] = presence_penalty
        if min_p is not None:
            extra_body_params["min_p"] = min_p
        if top_k is not None:
            extra_body_params["top_k"] = top_k
        if top_p is not None:
            # top_p 是标准参数，但某些 provider 可能需要特殊处理
            base_params["top_p"] = top_p

        # 只有当有扩展参数时才添加 extra_body
        if extra_body_params:
            base_params["extra_body"] = extra_body_params

        # 使用适配器调整参数
        adapted_params = self._adapter.adapt_create_params(
            base_params, enable_thinking)

        logger.info(f"[{self._provider}] 调用参数: model={model}, enable_thinking={enable_thinking}, "
                    f"supports_native_thinking={self._adapter.capabilities.supports_enable_thinking}")

        # 打印完整请求体（排除messages内容以避免日志过长）
        log_params = adapted_params.copy()
        if 'messages' in log_params:
            log_params['messages'] = f"<{len(log_params['messages'])} messages>"
        logger.info(f"[{self._provider}] 请求体: {log_params}")

        # type: ignore[]
        return await self._client.chat.completions.create(**adapted_params)

    async def call(  # noqa: C901, PLR0912, PLR0913
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        temperature: float | None = None,
        *,
        streaming: bool = True,
        result_only: bool = True,
        model: str | None = None,
        enable_thinking: bool = False,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        min_p: float | None = None,
        top_k: int | None = None,
        top_p: float | None = None,
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
        stream = await self._create_stream(
            msg_list,
            max_tokens,
            temperature,
            model,
            enable_thinking,
            frequency_penalty,
            presence_penalty,
            min_p,
            top_k,
            top_p,
        )
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

        # 如果streaming模式下没有返回任何text，至少返回一个空格
        # 避免下游处理空字符串时出错
        if streaming and not result:
            logger.warning("[Reasoning] 模型没有返回任何文本内容，返回占位符")
            yield " "

        # 更新token统计
        if self.input_tokens == 0 or self.output_tokens == 0:
            self.input_tokens = TokenCalculator().calculate_token_length(
                messages,
            )
            self.output_tokens = TokenCalculator().calculate_token_length(
                [{"role": "assistant", "content": result}],
                pure_text=True,
            )
