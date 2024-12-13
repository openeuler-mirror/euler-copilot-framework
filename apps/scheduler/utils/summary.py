# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
# 使用大模型生成对话总结

from __future__ import annotations
from typing import List

from apps.llm import get_llm, get_message_model


class Summary:
    system_prompt = """Progressively summarize the lines of conversation provided, adding onto the previous summary \
returning a new summary. Summary should be less than 2000 words. Examples are given below.

EXAMPLE
## Previous Summary

人类询问AI有关openEuler容器平台应当使用哪个软件的问题，AI向其推荐了iSula安全容器平台。

## Conversations

### User

iSula有什么特点？

### Assistant

iSula 的特点如下:
轻量语言：C/C++，Rust on the way
北向接口：提供CRI接口，支持对接Kubernetes; 同时提供便捷使用的命令行
南向接口：支持OCI runtime和镜像规范，支持平滑替换
容器形态：支持系统容器、虚机容器等多种容器形态
扩展能力：提供插件化架构，可根据用户需要开发定制化插件

### Used Tool

- name: Search
- description: 查询关键字对应的openEuler产品简介。
- output: `{"total":1,"data":["iSula是openEuler推出的一个安全容器运行平台。"]}`

## Summary
人类询问AI有关openEuler容器平台应当使用哪个软件的问题，AI向其推荐了iSula安全容器平台。人类询问iSula有何特点，\
AI使用Search工具搜索了“iSula”关键字，获得了1条搜索结果，即iSula的定义。AI列举了轻量语言、北向接口、\
南向接口、容器形态、扩展能力五种特点。

END OF EXAMPLE"""
    user_prompt = """## Previous Summary
{last_summary}

## Conversations

### User

{user_question}

### Assistant

{llm_output}

### Used Tool

- name: {tool_name}
- description: {tool_description}
- output: `{tool_output}`

## Summary
"""

    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None):
        if system_prompt is not None:
            self.system_prompt = system_prompt
        if user_prompt is not None:
            self.user_prompt = user_prompt

    async def generate_summary(self, last_summary: str, qa_pair: List[str], tool_info: List[str]) -> str:
        llm = get_llm()
        msg_cls = get_message_model(llm)

        messages = [
            msg_cls(role="system", content=self.system_prompt),
            msg_cls(role="user", content=self.user_prompt.format(
                last_summary=last_summary,
                user_question=qa_pair[0],
                llm_output=qa_pair[1],
                tool_name=tool_info[0],
                tool_description=tool_info[1],
                tool_output=tool_info[2]
            ))
        ]

        result = llm.invoke(messages)
        return result.content
