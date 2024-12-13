# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
# 使用大模型进行结果评价

from __future__ import annotations
from typing import Tuple

import sglang
import openai

from apps.llm import get_scheduler, create_vllm_stream, stream_to_str


class Evaluate:
    system_prompt = """You are an expert evaluation system for a tool calling chatbot.
You are given the following information:
- a user query, and
- a tool output

You may also be given a reference description to use for reference in your evaluation.

Your job is to judge the relevance and correctness of the tool output. \
Output a single score that represents a holistic evaluation. You must return your response in a line with only the score. \
Do not return answers in any other format. On a separate line provide your reasoning for the score as well.

Follow these guidelines for scoring:
- Your score has to be between 1 and 5, where 1 is the worst and 5 is the best.
- If the tool output is not relevant to the user query, you should give a score of 1.
- If the tool output is relevant but contains mistakes, you should give a score between 2 and 3.
- If the tool output is relevant and fully correct, you should give a score between 4 and 5.
- If 'error', code '500', 'failed' appeared in the tool output, it's more likely a mistake, you should give a score lower than 3.
- If 'success', code '200', 'succeed' appeared in the tool output, it's more likely a correct output, you should give a score higher than 4.

Example response is given below:

EXAMPLE
## Score

4.0

## Reason

The tool output is relevant to the user query, \
but it made up the data for one field and didn't use the default value from the reference description.

END OF EXAMPLE"""
    user_prompt = """## User Query

{user_question}

## Tool Output

{tool_output}

## Reference Description

{tool_description}"""


    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None):
        if system_prompt is not None:
            self.system_prompt = system_prompt
        if user_prompt is not None:
            self.user_prompt = user_prompt

    @staticmethod
    @sglang.function
    def _generate_evaluation_sglang(s, system_prompt: str, user_prompt: str, user_question: str, tool_output: str, tool_description: str):
        s += sglang.system(system_prompt)

        s += sglang.user(user_prompt.format(
            user_question=user_question,
            tool_output=tool_output,
            tool_description=tool_description
        ))

        s += sglang.assistant_begin()
        s += "## Score\n\n" + sglang.gen(name="score", regex=r"[\d]\.[\d]") + "\n\n"
        s += "## Reason\n\n" + sglang.gen(name="reason", max_tokens=500)
        s += sglang.assistant_end()

    async def _generate_evaluation_vllm(self, backend: openai.AsyncOpenAI, user_question: str,
                                        tool_output: str, tool_description: str) -> Tuple[float, str]:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(
                user_question=user_question,
                tool_output=tool_output,
                tool_description=tool_description
            )}
        ]

        stream = await create_vllm_stream(backend, messages, max_tokens=50, extra_body={
            "guided_regex": r"## Score\n\n[0-5].[0-9]"
        })
        score = await stream_to_str(stream)[-3:]

        messages += [
            {"role": "assistant", "content": score},
            {"role": "user", "content": "## Reason\n\n"}
        ]

        stream = await create_vllm_stream(backend, messages, max_tokens=500, extra_body={})
        reason = await stream_to_str(stream)

        return float(score), reason

    async def generate_evaluation(self, user_question: str, tool_output: str, tool_description: str) -> Tuple[float, str]:
        backend = get_scheduler()
        if isinstance(backend, sglang.RuntimeEndpoint):
            sglang.set_default_backend(backend)
            state = Evaluate._generate_evaluation_sglang.run(
                system_prompt=self.system_prompt,
                user_prompt=self.user_prompt,
                user_question=user_question,
                tool_output=tool_output,
                tool_description=tool_description,
                stream=True
            )

            reason = ""
            async for chunk in state.text_async_iter(var_name="reason"):
                reason += chunk

            score = float(state["score"])
            return score, reason
        else:
            return await self._generate_evaluation_vllm(backend, user_question, tool_output, tool_description)
