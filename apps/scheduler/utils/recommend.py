# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
# 使用大模型进行问题改写

from __future__ import annotations

from apps.llm import get_llm, get_message_model


class Recommend:
    system_prompt: str = """依照给出的工具描述和其他信息，生成符合用户目标的改写问题，或符合逻辑的预测问题。生成的问题将用于指导用户进行下一步的提问。
要求：
1. 以用户身份进行问题生成。
2. 工具描述的优先级高于用户问题或用户目标。当工具描述和用户问题相关性较小时，优先使用工具描述结合其他信息进行预测问题生成。
3. 必须为疑问句或祈使句。
4. 不得超过30个字。
5. 不要输出任何额外信息。

下面是一组示例：

EXAMPLE
## 工具描述
查询天气数据
    
## 背景信息
人类向AI询问杭州的著名旅游景点，大模型提供了杭州西湖、杭州钱塘江等多个著名景点的信息。
    
## 问题
帮我查询今天的杭州天气数据
END OF EXAMPLE"""
    user_prompt: str = """
## 工具描述
{action_description}

## 背景信息
{background}

## 问题
"""

    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None):
        if system_prompt is not None:
            self.system_prompt = system_prompt
        if user_prompt is not None:
            self.user_prompt = user_prompt

    async def recommend(self, action_description: str, background: str = "Empty.") -> str:
        llm = get_llm()
        msg_cls = get_message_model(llm)

        messages = [
            msg_cls(role="system", content=self.system_prompt),
            msg_cls(role="user", content=self.user_prompt.format(
                action_description=action_description,
                background=background
            ))
        ]

        result = llm.invoke(messages)
        return result.content
