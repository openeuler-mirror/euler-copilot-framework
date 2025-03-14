"""用于FunctionCall的大模型

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
from typing import Any

from asyncer import asyncify

from apps.common.config import config
from apps.constants import REASONING_BEGIN_TOKEN, REASONING_END_TOKEN
from apps.scheduler.json_schema import build_regex_from_schema


class FunctionLLM:
    """用于FunctionCall的模型"""

    _client: Any

    def __init__(self) -> None:
        """初始化用于FunctionCall的模型

        目前支持：
        - sglang
        - vllm
        - ollama
        """
        if config["SCHEDULER_BACKEND"] == "sglang":
            import sglang
            from sglang.lang.chat_template import get_chat_template

            if not config["SCHEDULER_API_KEY"]:
                self._client = sglang.RuntimeEndpoint(config["SCHEDULER_URL"])
            else:
                self._client = sglang.RuntimeEndpoint(config["SCHEDULER_URL"], api_key=config["SCHEDULER_API_KEY"])
            self._client.chat_template = get_chat_template("chatml")

        if config["SCHEDULER_BACKEND"] == "vllm" or config["SCHEDULER_BACKEND"] == "openai":
            import openai
            if not config["SCHEDULER_API_KEY"]:
                self._client = openai.AsyncOpenAI(base_url=config["SCHEDULER_URL"] + "/v1")
            else:
                self._client = openai.AsyncOpenAI(
                    base_url=config["SCHEDULER_URL"] + "/v1",
                    api_key=config["SCHEDULER_API_KEY"],
                )

        if config["SCHEDULER_BACKEND"] == "ollama":
            import ollama
            if not config["SCHEDULER_API_KEY"]:
                self._client = ollama.AsyncClient(host=config["SCHEDULER_URL"])
            else:
                self._client = ollama.AsyncClient(
                    host=config["SCHEDULER_URL"],
                    headers={
                        "Authorization": f"Bearer {config['SCHEDULER_API_KEY']}",
                    },
                )

    @staticmethod
    def _sglang_func(s, messages: list[dict[str, Any]], schema: dict[str, Any], max_tokens: int, temperature: float) -> None:  # noqa: ANN001
        """构建sglang需要的执行函数

        :param s: sglang context
        :param messages: 历史消息
        :param schema: 输出JSON Schema
        :param max_tokens: 最大Token长度
        :param temperature: 大模型温度
        """
        for msg in messages:
            if msg["role"] == "user":
                s += s.user(msg["content"])
            elif msg["role"] == "assistant":
                s += s.assistant(msg["content"])
            elif msg["role"] == "system":
                s += s.system(msg["content"])
            else:
                err_msg = f"Unknown message role: {msg['role']}"
                raise ValueError(err_msg)

        # 如果Schema为空，认为是直接问答，不加输出限制
        if not schema:
            s += s.assistant(s.gen(name="output", max_tokens=max_tokens, temperature=temperature))
        else:
            s += s.assistant(s.gen(name="output", regex=build_regex_from_schema(json.dumps(schema)), max_tokens=max_tokens, temperature=temperature))


    async def _call_vllm(self, messages: list[dict[str, Any]], schema: dict[str, Any], max_tokens: int, temperature: float) -> str:
        """调用vllm模型生成JSON

        :param messages: 历史消息列表
        :param schema: 输出JSON Schema
        :param max_tokens: 最大Token长度
        :param temperature: 大模型温度
        :return: 生成的JSON
        """
        model = config["SCHEDULER_MODEL"]
        if not model:
            err_msg = "未设置FuntionCall所用模型！"
            raise ValueError(err_msg)

        param = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        # 如果Schema不为空，认为是FunctionCall，需要指定输出格式
        if schema:
            param["extra_body"] = {"guided_json": schema}

        chat = await self._client.chat.completions.create(**param)

        reasoning = False
        result = ""
        async for chunk in chat:
            chunk_str = chunk.choices[0].delta.content or ""
            for token in REASONING_BEGIN_TOKEN:
                if token in chunk_str:
                    reasoning = True
                    continue

            for token in REASONING_END_TOKEN:
                if token in chunk_str:
                    reasoning = False
                    continue

            if reasoning:
                result += chunk_str
        return result


    async def _call_openai(self, messages: list[dict[str, Any]], schema: dict[str, Any], max_tokens: int, temperature: float) -> str:
        """调用openai模型生成JSON

        :param messages: 历史消息列表
        :param schema: 输出JSON Schema
        :param max_tokens: 最大Token长度
        :param temperature: 大模型温度
        :return: 生成的JSON
        """
        model = config["SCHEDULER_MODEL"]
        if not model:
            err_msg = "未设置FuntionCall所用模型！"
            raise ValueError(err_msg)

        param = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if schema:
            tool_data = {
                "type": "function",
                "function": {
                    "name": "output",
                    "description": "Call the function to get the output",
                    "parameters": schema,
                },
            }
            param["tools"] = [tool_data]
            param["tool_choice"] = "required"

        response = await self._client.chat.completions.create(**param)
        try:
            ans = response.choices[0].message.tool_calls[0].function.arguments or ""
        except IndexError:
            ans = ""
        return ans


    async def _call_ollama(self, messages: list[dict[str, Any]], schema: dict[str, Any], max_tokens: int, temperature: float) -> str:
        """调用ollama模型生成JSON

        :param messages: 历史消息列表
        :param schema: 输出JSON Schema
        :param max_tokens: 最大Token长度
        :param temperature: 大模型温度
        :return: 生成的对话回复
        """
        param = {
            "model": config["SCHEDULER_MODEL"],
            "messages": messages,
            "options": {
                "temperature": temperature,
                "num_ctx": max_tokens,
                "num_predict": max_tokens,
            },
        }
        # 如果Schema不为空，认为是FunctionCall，需要指定输出格式
        if schema:
            param["format"] = schema

        response = await self._client.chat(**param)
        return response.message.content or ""


    async def _call_sglang(self, messages: list[dict[str, Any]], schema: dict[str, Any], max_tokens: int, temperature: float) -> str:
        """调用sglang模型生成JSON

        :param messages: 历史消息
        :param schema: 输出JSON Schema
        :param max_tokens: 最大Token长度
        :param temperature: 大模型温度
        :return: 生成的JSON
        """
        # 构造sglang执行函数
        import sglang
        sglang.set_default_backend(self._client)

        sglang_func = sglang.function(self._sglang_func)
        state = await asyncify(sglang_func.run)(messages, schema, max_tokens, temperature)  #type: ignore[arg-type]
        return state["output"]


    async def call(self, **kwargs) -> str:  # noqa: ANN003
        """调用FunctionCall小模型

        暂不开放流式输出
        """
        if config["SCHEDULER_BACKEND"] == "vllm":
            json_str = await self._call_vllm(**kwargs)

        elif config["SCHEDULER_BACKEND"] == "sglang":
            json_str = await self._call_sglang(**kwargs)

        elif config["SCHEDULER_BACKEND"] == "ollama":
            json_str = await self._call_ollama(**kwargs)

        else:
            err = "未知的Function模型后端"
            raise ValueError(err)

        return json_str
