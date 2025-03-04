"""问答大模型调用

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import logging
from collections.abc import AsyncGenerator
from typing import Optional

import ray
import tiktoken
from openai import AsyncOpenAI

from apps.common.config import config
from apps.constants import REASONING_BEGIN_TOKEN, REASONING_END_TOKEN

logger = logging.getLogger("ray")


class ReasoningLLM:
    """调用用于问答的大模型"""

    _encoder = tiktoken.get_encoding("cl100k_base")

    def __init__(self) -> None:
        """判断配置文件里用了哪种大模型；初始化大模型客户端"""
        if not config["LLM_KEY"]:
            self._client = AsyncOpenAI(
                base_url=config["LLM_URL"],
            )
            return

        self._client =  AsyncOpenAI(
            api_key=config["LLM_KEY"],
            base_url=config["LLM_URL"],
        )

    def _calculate_token_length(self, messages: list[dict[str, str]], *, pure_text: bool = False) -> int:
        """使用ChatGPT的cl100k tokenizer，估算Token消耗量"""
        result = 0
        if not pure_text:
            result += 3 * (len(messages) + 1)

        for msg in messages:
            result += len(self._encoder.encode(msg["content"]))

        return result

    def _validate_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """验证消息格式是否正确"""
        if messages[0]["role"] != "system":
            # 添加默认系统消息
            messages.insert(0, {"role": "system", "content": "You are a helpful assistant."})

        if messages[-1]["role"] != "user":
            err = f"消息格式错误，最后一个消息必须是用户消息：{messages[-1]}"
            raise ValueError(err)

        return messages

    async def call(self, task_id: str, messages: list[dict[str, str]],  # noqa: C901
                   max_tokens: Optional[int] = None, temperature: Optional[float] = None,
                   *, streaming: bool = True, result_only: bool = True) -> AsyncGenerator[str, None]:
        """调用大模型，分为流式和非流式两种"""
        input_tokens = self._calculate_token_length(messages)
        try:

            msg_list = self._validate_messages(messages)
        except ValueError as e:
            err = f"消息格式错误：{e}"
            raise ValueError(err) from e

        if max_tokens is None:
            max_tokens = config["LLM_MAX_TOKENS"]
        if temperature is None:
            temperature = config["LLM_TEMPERATURE"]

        stream = await self._client.chat.completions.create(
            model=config["LLM_MODEL"],
            messages=msg_list,     # type: ignore[]
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )     # type: ignore[]

        reasoning_content = ""
        result = ""

        is_first_chunk = True
        is_reasoning = False
        reasoning_type = ""

        async for chunk in stream:
            # 当前Chunk内的信息
            reason = ""
            text = ""

            if is_first_chunk:
                if hasattr(chunk.choices[0].delta, "reasoning_content"):
                    reason = "<think>" + chunk.choices[0].delta.reasoning_content or ""
                    reasoning_type = "args"
                    is_reasoning = True
                else:
                    for token in REASONING_BEGIN_TOKEN:
                        if token == (chunk.choices[0].delta.content or ""):
                            reason = "<think>"
                            reasoning_type = "tokens"
                            is_reasoning = True
                            break

            # 当前已经不是第一个Chunk了
            is_first_chunk = False

            # 当前是正常问答
            if not is_reasoning:
                text = chunk.choices[0].delta.content or ""

            # 当前处于推理状态
            if not is_first_chunk and is_reasoning:
                # 如果推理内容用特殊参数传递
                if reasoning_type == "args":
                    # 还在推理
                    if hasattr(chunk.choices[0].delta, "reasoning_content"):
                        reason = chunk.choices[0].delta.reasoning_content or ""
                    # 推理结束
                    else:
                        is_reasoning = False
                        reason = "</think>"

                # 如果推理内容用特殊token传递
                elif reasoning_type == "tokens":
                    # 结束推理
                    for token in REASONING_END_TOKEN:
                        if token == (chunk.choices[0].delta.content or ""):
                            is_reasoning = False
                            reason = "</think>"
                            text = ""
                            break
                    # 还在推理
                    if is_reasoning:
                        reason = chunk.choices[0].delta.content or ""

            # 推送消息
            if streaming:
                # 如果需要推送推理内容
                if reason and not result_only:
                    yield reason

                # 推送text
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

        output_tokens = self._calculate_token_length([{"role": "assistant", "content": result}], pure_text=True)
        task = ray.get_actor("task")
        await task.update_token_summary.remote(task_id, input_tokens, output_tokens)
