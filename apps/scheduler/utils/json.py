# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from __future__ import annotations
import json
from typing import Dict, Any
import logging
from datetime import datetime
import pytz
import re

import sglang
import openai

from apps.llm import get_scheduler, create_vllm_stream, stream_to_str, get_llm, get_message_model, get_json_code_block
from apps.scheduler.gen_json import gen_json

logger = logging.getLogger('gunicorn.error')


class Json:
    system_prompt = r"""You must call the following function one time to answer the given question. For each function call \
return a valid json object with only function parameters.

Output must be in <tool_call>{ }</tool_call> XML tags. For example:
<tool_call>{"parameter_name": "value"}</tool_call>

Requirements:
- Output as few parameters as possible, and avoid using optional parameters in the generated results unless necessary.
- If a parameter is not mentioned in the user's instruction, use its default value.
- If no default value is specified, use `0` for integers, `0.0` for numbers, `null` for strings, `[]` for arrays \
and `{}` for objects.
- Don’t make up parameters. Values can only be obtained from given user input, background information, and JSON Schema.
- The example values are only used to demonstrate the data format. Do not fill the example values in the generated results.

Here is an example:

EXAMPLE
## Question
查询杭州天气信息

## Parameters JSON Schema

```json
{"properties":{"city":{"type":"string","example":"London","default":"London","description":"City name."},"country":{"type":"string","example":"UK","description":"Optional parameter. If not set, auto-detection is performed."},"date":{"type":"string","example":"2024-09-01","description":"The date of the weather."},"meter":{"type":"integer","default":"c","description":"If the units are in Celsius, the value is \"c\"; if the units are in Fahrenheit, the value is \"f\".","enum":["c","f"]}},"required":["city","meter"]}
```

## Background Information

Empty.

## Current Time

2024-09-02 10:00:00

## Thought

The user needs to query the weather information of Hangzhou. According to the given JSON Schema, city and meter are required parameters. The user did not explicitly provide the query date, so date should be empty. The user is querying the weather in Hangzhou, so the value of city should be Hangzhou. The user did not specify the temperature unit type, so the default value "c" is used.

## Result

```json
{"city": "Hangzhou", "meter": "c"}
```
END OF EXAMPLE"""
    user_prompt = """## Question

{question}

## Parameters JSON Schema

```json
{spec_data}
```

## Background Information

{background}

## Current Time
{time}"""


    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None):
        if system_prompt is not None:
            self.system_prompt = system_prompt
        if user_prompt is not None:
            self.user_prompt = user_prompt

    @staticmethod
    @sglang.function
    def _generate_json_sglang(s, system_prompt: str, user_prompt: str, background: str, question: str, spec_regex: str, spec: str):
        s += sglang.system(system_prompt)
        s += sglang.user(user_prompt.format(
            question=question,
            spec_data=spec,
            background=background,
            time=datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        ) + "# Thought\n\n")

        s += sglang.assistant(sglang.gen(max_tokens=1000, temperature=0.5))
        s += sglang.user("## Result\n\n")
        s += sglang.assistant("<tool_call>" + \
                              sglang.gen(name="data", max_tokens=1000, regex=spec_regex, temperature=0.01) \
                              + "</tool_call>")

    async def _generate_json_vllm(self, backend: openai.AsyncOpenAI, background: str, question: str, spec: str) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(
                question=question,
                spec_data=spec,
                background=background,
                time=datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
            ) + "# Thought\n\n"},
            {"role": "assistant", "content": "<tool_call>"},
        ]

        stream = await create_vllm_stream(backend, messages, max_tokens=1000, extra_body={
            "guided_json": spec,
            "guided_decoding_backend": "lm-format-enforcer"
        })

        json_str = await stream_to_str(stream)
        return json_str

    @staticmethod
    def _remove_null_params(input_val):
        if isinstance(input_val, dict):
            new_dict = {}
            for key, value in input_val.items():
                nested = Json._remove_null_params(value)
                if isinstance(nested, bool) or isinstance(nested, int) or isinstance(nested, float):
                    new_dict[key] = nested
                elif nested:
                    new_dict[key] = nested
            return new_dict
        elif isinstance(input_val, list):
            new_list = []
            for v in input_val:
                cleaned_v = Json._remove_null_params(v)
                if cleaned_v:
                    new_list.append(cleaned_v)
            if len(new_list) > 0:
                return new_list
        else:
            return input_val

    @staticmethod
    def _check_json_valid(spec: dict, json_data: dict):
        pass

    async def generate_json(self, background: str, question: str, spec: dict) -> Dict[str, Any]:
        spec_regex = gen_json(spec)
        if not spec_regex:
            spec_regex = "{}"
        logger.info(f"JSON正则：{spec_regex}")

        if not background:
            background = "Empty."

        llm = get_llm()
        msg_cls = get_message_model(llm)
        messages = [
            msg_cls(role="system", content="""## Role

You are a assistant who generates API call parameters. Your task is generating API call parameters according to the JSON Schema and user input.
The call parameters must be in JSON format and must be wrapped in the following Markdown code block:

```json
// Here are the generated JSON parameters.
```

## Requirements

When generating, You must follow these requirements:

1. Use as few parameters as possible. Optional parameters should be 'null' unless it's necessary. e.g. `{"search_key": null}`
2. The order of keys in the generated JSON data must be the same as the order in the JSON Schema.
3. Do not add comments, instructions, or other irrelevant text to the generated code block;
4. Don’t make up parameters, don’t assume parameters. The value of the parameter can only be obtained from the given user input, background information and JSON Schema.
5. Before generating JSON, give your thought of the given question. Be helpful and concise.
6. Output strictly in the format described by JSON Schema.
7. The examples are only used to demonstrate the data format. Do not use the examples directly in the generated results."""),
            msg_cls(role="user", content=self.user_prompt.format(
                question=question,
                spec_data=spec,
                background=background,
                time=datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
            ) + "\n\nLet's think step by step.")
        ]

        result = llm.invoke(messages).content
        logger.info(f"生成的JSON参数为：{result}")
        try:
            result_str = get_json_code_block(result)

            if not re.match(spec_regex, result_str):
                raise ValueError("JSON not valid.")
            data = Json._remove_null_params(json.loads(result_str))

            return data
        except Exception as e:
            logger.error(f"直接生成JSON失败：{e}")


        backend = get_scheduler()
        if isinstance(backend, sglang.RuntimeEndpoint):
            sglang.set_default_backend(backend)
            state = Json._generate_json_sglang.run(
                system_prompt=self.system_prompt,
                user_prompt=self.user_prompt,
                background=background,
                question=question,
                spec_regex=spec_regex,
                spec=spec
            )

            result = ""
            async for chunk in state.text_async_iter(var_name="data"):
                result += chunk
            logger.info(f'Structured Output生成的参数为: {result}')
            return Json._remove_null_params(json.loads(result))
        else:
            spec_str = json.dumps(spec, ensure_ascii=False)
            result = await self._generate_json_vllm(backend, background, question, spec_str)
            logger.info(f"Structured Output生成的参数为：{result}")
            return Json._remove_null_params(json.loads(result))
