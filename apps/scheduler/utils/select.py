# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
# 使用大模型选择Top N最匹配语义的项

from __future__ import annotations

import asyncio
from typing import List, Any, Dict

import sglang
import openai

from apps.llm import create_vllm_stream, get_scheduler, stream_to_str
from apps.common.thread import ProcessThreadPool


class Select:
    system_prompt = """Your task is: choose the tool that best matches user instructions and contextual information \
based on the description of the tool.

Tool name and its description will be given in the format:

```xml
<tools>
    <item>
        <name>Tool Name</name>
        <description>Tool Description</description>
    </item>
</tools>
```

Here are some examples:

EXAMPLE

## Instruction

使用天气API，查询明天的天气信息

## Tools

```xml
<tools>
    <item>
        <name>API</name>
        <description>请求特定API，获得返回的JSON数据</description>
    </item>
    <item>
        <name>SQL</name>
        <description>查询数据库，获得table中的数据</description>
    </item>
</tools>
```

## Thinking

Let's think step by step. There's no tool available to get weather forecast directly, so I need to try using other \
tools to obtain weather information. API tools can retrieve external data through the use of APIs, and weather \
information may be stored in external data. As the user instructions explicitly mentioned the use of the weather API, \
the API tool should be prioritized. SQL tools are used to retrieve information from databases. Given the variable \
and dynamic nature of weather data, it is unlikely to be stored in a database. Therefore, the priority of \
SQL tools is relatively low.

## Answer

Thus the selected tool is: API.

END OF EXAMPLE"""
    user_prompt = """## Instruction

{question}

## Tools

```xml
{tools}
```

## Thinking

Let's think step by step."""

    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None):
        if system_prompt is not None:
            self.system_prompt = system_prompt
        if user_prompt is not None:
            self.user_prompt = user_prompt

    @staticmethod
    def _flows_to_xml(choice: List[Dict[str, Any]]) -> str:
        result = "<tools>\n"
        for tool in choice:
            result += "\t<item>\n\t\t<name>{name}</name>\n\t\t<description>{description}</description>\n\t</item>\n".format(
                name=tool["name"], description=tool["description"]
            )
        result += "</tools>"
        return result

    @staticmethod
    @sglang.function
    def _top_flows_sglang(s, system_prompt: str, user_prompt: str, choice: List[Dict[str, Any]], instruction: str):
        s += sglang.system(system_prompt)
        s += sglang.user(user_prompt.format(
            question=instruction,
            tools=Select._flows_to_xml(choice),
        ))
        s += sglang.assistant(sglang.gen(max_tokens=1500, stop="\n\n"))
        s += sglang.user("\n\n##Answer\n\nThus the selected tool is: ")
        s += sglang.assistant_begin()

        choice_list = []
        for item in choice:
            choice_list.append(item["name"])
        s += sglang.gen(choices=choice_list, name="choice")
        s += sglang.assistant_end()

    async def _top_flows_vllm(self, backend: openai.AsyncOpenAI, choice: List[Dict[str, Any]], instruction: str) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(
                question=instruction,
                tools=Select._flows_to_xml(choice),
            )}
        ]

        stream = await create_vllm_stream(backend, messages, max_tokens=1500, extra_body={})
        result = await stream_to_str(stream)

        messages += [
            {"role": "assistant", "content": result},
            {"role": "user", "content": "## Answer\n\nThus the selected tool is: "}
        ]

        choice_regex = "("
        for item in choice:
            choice_regex += item["name"] + "|"
        choice_regex = choice_regex.rstrip("|") + ")"

        stream = await create_vllm_stream(backend, messages, max_tokens=200, extra_body={
            "guided_regex": choice_regex
        })
        result = await stream_to_str(stream)

        return result

    async def top_flow(self, choice: List[Dict[str, Any]], instruction: str) -> str:
        backend = get_scheduler()
        if isinstance(backend, sglang.RuntimeEndpoint):
            sglang.set_default_backend(backend)
            state_future = ProcessThreadPool().thread_executor.submit(
                Select._top_flows_sglang.run,
                system_prompt=self.system_prompt,
                user_prompt=self.user_prompt,
                choice=choice,
                instruction=instruction
            )
            state = await asyncio.wrap_future(state_future)
            return state["choice"]
        else:
            return await self._top_flows_vllm(backend, choice, instruction)
