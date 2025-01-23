"""推理/生成大模型调用

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from collections.abc import AsyncGenerator

import tiktoken
from openai import AsyncOpenAI

from apps.common.config import config
from apps.common.singleton import Singleton
from apps.manager.task import TaskManager


class ReasoningLLM(metaclass=Singleton):
    """调用用于推理/生成的大模型"""

    _encoder = tiktoken.get_encoding("cl100k_base")

    def __init__(self) -> None:
        """判断配置文件里用了哪种大模型；初始化大模型客户端"""
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

    async def call(self, task_id: str, messages: list[dict[str, str]],
                   max_tokens: int = 8192, temperature: float = 0.07, *, streaming: bool = True) -> AsyncGenerator[str, None]:
        """调用大模型，分为流式和非流式两种"""
        input_tokens = self._calculate_token_length(messages)
        try:
            msg_list = self._validate_messages(messages)
        except ValueError as e:
            err = f"消息格式错误：{e}"
            raise ValueError(err) from e

        stream = await self._client.chat.completions.create(
            model=config["LLM_MODEL"],
            messages=msg_list,     # type: ignore[]
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )     # type: ignore[]

        if streaming:
            result = ""
            async for chunk in stream:
                text = chunk.choices[0].delta.content or ""
                yield text
                result += text
        else:
            result = ""
            async for chunk in stream:
                result += chunk.choices[0].delta.content or ""
            yield result

        output_tokens = self._calculate_token_length([{"role": "assistant", "content": result}], pure_text=True)
        await TaskManager.update_token_summary(task_id, input_tokens, output_tokens)
