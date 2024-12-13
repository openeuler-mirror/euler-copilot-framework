# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
# 使用大模型的随机化+投票方式选择最优答案

from __future__ import annotations
from typing import List, Dict, Any, Tuple
import asyncio
from collections import Counter

import sglang
import openai

from apps.common.thread import ProcessThreadPool
from apps.llm import get_scheduler, create_vllm_stream, stream_to_str


class Consistency:
    system_prompt: str = """Your task is: choose the answer that best matches user instructions and contextual information. \
The instruction and context information will be given in a certain format. Here are some examples:

EXAMPLE
## Instruction

用户是否询问了openEuler相关知识？

## Context

User asked whether iSula is better than Docker. iSula is a tool developed by the openEuler Community. iSula contains \
features such as security-enhanced containers, performance optimizations and openEuler compatibility.

## Choice

The available choices are:

- Yes
- No

## Thought

Let's think step by step. User mentioned 'iSula', which is a tool related to the openEuler Community. So the user \
question is related to openEuler.

## Answer

Yes

END OF EXAMPLE"""
    user_prompt: str = """## Instruction

{question}

## Context

{background}
Previous Output: {data}

## Choice

The available choices are:

{choice_list}

## Thought
"""

    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None):
        if system_prompt is not None:
            self.system_prompt = system_prompt
        if user_prompt is not None:
            self.user_prompt = user_prompt

    @staticmethod
    def _choices_to_prompt(choices: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
        choices_prompt = ""
        choice_str_list = []
        for choice in choices:
            choices_prompt += "- {}: {}\n".format(choice["step"], choice["description"])
            choice_str_list.append(choice["step"])
        return choices_prompt, choice_str_list

    @staticmethod
    @sglang.function
    def _generate_consistency_sglang(s, system_prompt: str, user_prompt: str, instruction: str,
                                     background: str, data: Dict[str, Any], choices: List[Dict[str, Any]], answer_num: int):
        s += sglang.system(system_prompt)

        choice_prompt, choice_str_list = Consistency._choices_to_prompt(choices)

        s += sglang.user(user_prompt.format(
            question=instruction,
            background=background,
            choice_list=choice_prompt,
            data=data
        ))
        forks = s.fork(answer_num)

        for i, f in enumerate(forks):
            f += sglang.assistant_begin()
            f += "Let's think step by step. " + sglang.gen(max_tokens=512, stop="\n\n")
            f += "\n\n## Answer\n\n" + sglang.gen(choices=choice_str_list, name="result")
            f += sglang.assistant_end()

        result_list = []
        for item in forks:
            result_list.append(item["result"])

        s["major"] = result_list

    async def _generate_consistency_vllm(self, backend: openai.AsyncOpenAI, instruction: str, background: str, data: Dict[str, Any], choices: List[Dict[str, Any]], answer_num: int) -> List[str]:
        choice_prompt, choice_str_list = Consistency._choices_to_prompt(choices)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(
                question=instruction,
                background=background,
                data=data,
                choice_list=choice_prompt
            ) + "\nLet's think step by step."},
        ]

        result_list = []
        for i in range(answer_num):
            message_branch = messages
            stream = await create_vllm_stream(backend, message_branch, max_tokens=512, extra_body={})
            reasoning = await stream_to_str(stream)
            message_branch += [
                {"role": "assistant", "content": reasoning},
                {"role": "user", "content": "## Answer\n\n"}
            ]

            choice_regex = "("
            for choice in choice_str_list:
                choice_regex += choice + "|"
            choice_regex = choice_regex.rstrip("|") + ")"

            stream = await create_vllm_stream(backend, message_branch, max_tokens=16, extra_body={
                "guided_regex": choice_regex
            })
            result_list.append(await stream_to_str(stream))

        return result_list

    async def consistency(self, instruction: str, background: str, data: Dict[str, Any], choices: List[Dict[str, Any]], answer_num: int = 3) -> str:
        backend = get_scheduler()
        if isinstance(backend, openai.AsyncOpenAI):
            result_list = await self._generate_consistency_vllm(backend, instruction, background, data, choices, answer_num)
        else:
            sglang.set_default_backend(backend)
            state_future = ProcessThreadPool().thread_executor.submit(
                Consistency._generate_consistency_sglang.run,
                instruction=instruction, choices=choices, answer_num=answer_num,
                system_prompt=self.system_prompt, user_prompt=self.user_prompt,
                background=background, data=data
            )
            state = await asyncio.wrap_future(state_future)
            result_list = state["major"]

        count = Counter(result_list)
        return count.most_common(1)[0][0]
