# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from __future__ import annotations

from apps.llm import get_llm, get_message_model


class BackProp:
    system_prompt: str = """根据提供的错误日志、评估结果和背景信息，优化原始用户输入内容。

要求：
1. 优化后的用户输入能够最大程度避免错误，同时其中的数据保持与原始用户输入一致。
2. 不得编造数据。所有数据必须从原始用户输入和背景信息中获得。
3. 优化后的用户输入应最大程度上保留原始用户输入中的所有信息，不要遗漏数据或细节。"""
    user_prompt: str = """## 原始用户输入
{user_input}

## 错误日志
{exception}

## 评估结果
{evaluation}

## 背景信息
{background}

## 优化后的用户输入
"""

    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None):
        if system_prompt is not None:
            self.system_prompt = system_prompt
        if user_prompt is not None:
            self.user_prompt = user_prompt

    async def backprop(self, user_input: str, exception: str, evaluation: str, background: str) -> str:
        llm = get_llm()
        msg_cls = get_message_model(llm)
        messages = [
            msg_cls(role="system", content=self.system_prompt),
            msg_cls(role="user", content=self.user_prompt.format(
                user_input=user_input, exception=exception, evaluation=evaluation, background=background)
            )
        ]

        result = llm.invoke(messages).content
        return result
