"""问答大模型调用

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from collections.abc import AsyncGenerator
from typing import Optional

import tiktoken
from openai import AsyncOpenAI

from apps.common.config import config
from apps.common.singleton import Singleton
from apps.constants import REASONING_BEGIN_TOKEN, REASONING_END_TOKEN
from apps.manager.task import TaskManager


class ReasoningLLM(metaclass=Singleton):
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

    async def call(self, task_id: str, messages: list[dict[str, str]],  # noqa: C901, PLR0912
                   max_tokens: Optional[int] = None, temperature: Optional[float] = None,
                   *, streaming: bool = True) -> AsyncGenerator[str, None]:
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

        result = ""

        async for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            reason = ""
            if hasattr(chunk.choices[0].delta, "reasoning_content"):
                reason = chunk.choices[0].delta.reasoning_content or ""

            if reason:
                if "<think>" not in result:
                    reason = "<think>" + reason
                    result += reason
                    if streaming:
                        yield reason
                    continue
            else:
                if "<think>" in result and "</think>" not in result:
                    result += "</think>"
                    if streaming:
                        yield "</think>"

                for token in REASONING_BEGIN_TOKEN:
                    if token in content:
                        content = content.replace(token, "<think>")

                for token in REASONING_END_TOKEN:
                    if token in content:
                        content = content.replace(token, "</think>")

                result += content
                if streaming:
                    yield content

        if not streaming:
            yield result

        output_tokens = self._calculate_token_length([{"role": "assistant", "content": result}], pure_text=True)
        await TaskManager.update_token_summary(task_id, input_tokens, output_tokens)
