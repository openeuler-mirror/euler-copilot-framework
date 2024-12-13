# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
# 使用大模型进行解析和改错

from __future__ import annotations
from typing import Dict, Any
import json

import sglang
import openai

from apps.llm import get_scheduler, create_vllm_stream, stream_to_str


class Reflect:
    system_prompt = """You are an advanced reasoning agent that can improve based \
on self-reflection. You will be given a previous reasoning trial in which you are given a task and a action. \
You tried to accomplish the task with the certain action and generated input but failed. Your goal is to write a \
few sentences to explain why your attempt is wrong, and write a guidance according to your explanation. \
You will need this as guidance when you try again later. Only provide a few sentence description in your answer, \
not the future action and inputs.

Here are some examples:

EXAMPLE
## Previous Trial Instruction

查询机器192.168.100.1的CVE信息。

## Action

使用的工具是 A-Ops.CVE，作用为：查询特定主机IP的全部CVE信息。

## Action Input

```json
{"host_ip": "192.168.100.1", "num": 0}
```

## Observation

采取该Action后，输出的信息为空，不符合用户的指令要求。这可能是由请求参数设置不正确导致的结果，也可能是Action本身存在问题，或机器中并不存在CVE。

## Guidance

Action Input中，"num"字段被设置为了0。这个字段可能与最终显示的CVE条目数量有关。可以将该字段的值修改为100，再次尝试使用该接口。在获得有效的\
CVE信息后我，将继续后续步骤。我将继续优化Action Input，以获得更多符合用户指令的结果。

END OF EXAMPLE"""
    user_prompt = """## Previous Trial Instruction

{instruction}

## Action

{call}

## Action Input

```json
{call_input}
```

## Observation

{call_score_reason}

## Guidance"""

    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None):
        if system_prompt is not None:
            self.system_prompt = system_prompt
        if user_prompt is not None:
            self.user_prompt = user_prompt

    @staticmethod
    @sglang.function
    def _generate_reflect_sglang(s, system_prompt: str, user_prompt: str, instruction: str, call: str, call_input: str, call_score_reason: str):
        s += sglang.system(system_prompt)
        s += sglang.user(user_prompt.format(
            instruction=instruction,
            call=call,
            call_input=call_input,
            call_score_reason=call_score_reason
        ))
        s += sglang.assistant(sglang.gen(name="result", max_tokens=1500))

    async def _generate_reflect_vllm(self, backend: openai.AsyncOpenAI, instruction: str,
                                     call: str, call_input: str, call_score_reason: str) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(
                instruction=instruction,
                call_name=call,
                call_input=call_input,
                call_score_reason=call_score_reason
            )},
        ]

        stream = create_vllm_stream(backend, messages, max_tokens=1500, extra_body={})
        return await stream_to_str(stream)

    async def generate_reflect(self, instruction: str, call: Dict[str, Any], call_input: Dict[str, Any], call_score_reason: str) -> str:
        backend = get_scheduler()
        call_str = "使用的工具是 {}，作用为：{}".format(call["name"], call["description"])
        call_input_str = json.dumps(call_input, ensure_ascii=False)

        if isinstance(backend, sglang.RuntimeEndpoint):
            sglang.set_default_backend(backend)
            state = Reflect._generate_reflect_sglang.run(
                system_prompt=self.system_prompt,
                user_prompt=self.user_prompt,
                instruction=instruction,
                call=call_str,
                call_input=call_input_str,
                call_score_reason=call_score_reason,
                stream=True
            )

            result = ""
            async for chunk in state.text_async_iter(var_name="result"):
                result += chunk
            return result

        else:
            return await self._generate_reflect_vllm(backend, instruction, call_str, call_input_str, call_score_reason)
