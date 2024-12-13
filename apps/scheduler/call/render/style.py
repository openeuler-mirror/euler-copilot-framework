# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from __future__ import annotations
from typing import Dict, Any
import asyncio

import sglang
import openai

from apps.llm import get_scheduler, create_vllm_stream, stream_to_str
from apps.common.thread import ProcessThreadPool


class RenderStyle:
    system_prompt = """You are a helpful assistant. Help the user make style choices when drawing a chart.
Chart title should be short and less than 3 words.

Available styles:
- `bar`: Bar graph
- `pie`: Pie graph
- `line`: Line graph
- `scatter`: Scatter graph

Available bar graph styles:
- `normal`: Normal bar graph
- `stacked`: Stacked bar graph

Available pie graph styles:
- `normal`: Normal pie graph
- `ring`: Ring pie graph

Available scale styles:
- `linear`: Linear scale
- `log`: Logarithmic scale

Here are some examples:

EXAMPLE

## Question

查询数据库中的数据，并绘制堆叠柱状图。

## Thought

Let's think step by step. The user requires drawing a stacked bar chart, so the chart type should be `bar`, \
i.e. a bar chart; the chart style should be `stacked`, i.e. a stacked form.

## Answer

The chart style should be: bar
The bar graph style should be: stacked

END OF EXAMPLE
"""
    user_prompt = """## Question

{question}

## Thought
"""

    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None):
        if system_prompt is not None:
            self.system_prompt = system_prompt
        if user_prompt is not None:
            self.user_prompt = user_prompt

    @staticmethod
    @sglang.function
    def _generate_option_sglang(s, system_prompt: str, user_prompt: str, question: str):
        s += sglang.system(system_prompt)
        s += sglang.user(user_prompt.format(question=question))

        s += sglang.assistant_begin()
        s += "Let's think step by step:\n"
        for i in range(3):
            s += f"{i}. " + sglang.gen(max_tokens=200, stop="\n") + "\n"

        s += "## Answer\n\n"
        s += "The chart style should be: " + sglang.gen(choices=["bar", "scatter", "line", "pie"], name="style") + "\n"
        if s["style"] == "bar":
            s += "The bar graph style should be: " + sglang.gen(choices=["normal", "stacked"], name="add") + "\n"
            # 饼图只对第一列有效
        elif s["style"] == "pie":
            s += "The pie graph style should be: " + sglang.gen(choices=["normal", "ring"], name="add") + "\n"
        s += "The scale style should be: " + sglang.gen(choices=["linear", "log"], name="scale")
        s += sglang.assistant_end()

    async def _generate_option_vllm(self, backend: openai.AsyncOpenAI, question: str) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(question=question)},
        ]

        stream = await create_vllm_stream(backend, messages, max_tokens=200, extra_body={
            "guided_regex": r"## Answer\n\nThe chart style should be: (bar|pie|line|scatter)\n"
        })
        result = await stream_to_str(stream)

        result_dict = {}
        if "bar" in result:
            result_dict["style"] = "bar"
            messages += [
                {"role": "assistant", "content": result},
            ]
            stream = await create_vllm_stream(backend, messages, max_tokens=200, extra_body={
                "guided_regex": r"The bar graph style should be: (normal|stacked)\n"
            })
            result = await stream_to_str(stream)
            if "normal" in result:
                result_dict["add"] = "normal"
            elif "stacked" in result:
                result_dict["add"] = "stacked"
            messages += [
                {"role": "assistant", "content": result},
            ]
        elif "pie" in result:
            result_dict["style"] = "pie"
            messages += [
                {"role": "assistant", "content": result},
            ]
            stream = await create_vllm_stream(backend, messages, max_tokens=200, extra_body={
                "guided_regex": r"The pie graph style should be: (normal|ring)\n"
            })
            result = await stream_to_str(stream)
            if "normal" in result:
                result_dict["add"] = "normal"
            elif "ring" in result:
                result_dict["add"] = "ring"
            messages += [
                {"role": "assistant", "content": result},
            ]
        elif "line" in result:
            result_dict["style"] = "line"
        elif "scatter" in result:
            result_dict["style"] = "scatter"

        stream = await create_vllm_stream(backend, messages, max_tokens=200, extra_body={
            "guided_regex": r"The scale style should be: (linear|log)\n"
        })
        result = await stream_to_str(stream)
        if "linear" in result:
            result_dict["scale"] = "linear"
        elif "log" in result:
            result_dict["scale"] = "log"

        return result_dict

    async def generate_option(self, question: str) -> Dict[str, Any]:
        backend = get_scheduler()
        if isinstance(backend, sglang.RuntimeEndpoint):
            state_future = ProcessThreadPool().thread_executor.submit(
                RenderStyle._generate_option_sglang.run,
                question=question,
                system_prompt=self.system_prompt,
                user_prompt=self.user_prompt
            )
            state = await asyncio.wrap_future(state_future)
            result_dict = {
                "style": state["style"],
                "scale": state["scale"],
            }
            if state["style"] == "bar" or state["style"] == "pie":
                result_dict["add"] = state["add"]

            return result_dict

        else:
            return await self._generate_option_vllm(backend, question)