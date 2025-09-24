# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用于FunctionCall的大模型"""

import json
import logging
import re
from textwrap import dedent
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from jsonschema import Draft7Validator
from jsonschema import validate
from apps.common.config import Config
from apps.constants import JSON_GEN_MAX_TRIAL, REASONING_END_TOKEN
from apps.llm.prompt import JSON_GEN_BASIC

logger = logging.getLogger(__name__)


class FunctionLLM:
    """用于FunctionCall的模型"""

    def __init__(self) -> None:
        """
        初始化用于FunctionCall的模型

        目前支持：
        - vllm
        - ollama
        - function_call
        - json_mode
        - structured_output
        """
        # 暂存config；这里可以替代为从其他位置获取
        self._config = Config().get_config().function_call
        if not self._config.model:
            err_msg = "[FunctionCall] 未设置FuntionCall所用模型！"
            logger.error(err_msg)
            raise ValueError(err_msg)

        self._params = {
            "model": self._config.model,
            "messages": [],
            "extra_body": {"enable_thinking": False}
        }
        if self._config.backend != "ollama":
            self._params["timeout"] = 300
        if self._config.backend == "ollama":
            import ollama

            if not self._config.api_key:
                self._client = ollama.AsyncClient(host=self._config.endpoint)
            else:
                self._client = ollama.AsyncClient(
                    host=self._config.endpoint,
                    headers={
                        "Authorization": f"Bearer {self._config.api_key}",
                    },
                )

        else:
            import openai

            if not self._config.api_key:
                self._client = openai.AsyncOpenAI(
                    base_url=self._config.endpoint)
            else:
                self._client = openai.AsyncOpenAI(
                    base_url=self._config.endpoint,
                    api_key=self._config.api_key,
                )

    async def _call_openai(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """
        调用openai模型生成JSON

        :param list[dict[str, str]] messages: 历史消息列表
        :param dict[str, Any] schema: 输出JSON Schema
        :param int | None max_tokens: 最大Token长度
        :param float | None temperature: 大模型温度
        :return: 生成的JSON
        :rtype: str
        """
        self._params.update({
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })

        if self._config.backend == "vllm":
            self._params["extra_body"] = {"guided_json": schema}

        elif self._config.backend == "json_mode":
            logger.warning("[FunctionCall] json_mode无法确保输出格式符合要求，使用效果将受到影响")
            self._params["response_format"] = {"type": "json_object"}

        elif self._config.backend == "structured_output":
            self._params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "generate",
                    "description": "Generate answer based on the background information",
                    "schema": schema,
                    "strict": True,
                },
            }

        elif self._config.backend == "function_call":
            logger.warning("[FunctionCall] function_call无法确保一定调用工具，使用效果将受到影响")
            self._params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": "generate",
                        "description": "Generate answer based on the background information",
                        "parameters": schema,
                    },
                },
            ]

        # type: ignore[arg-type]
        response = await self._client.chat.completions.create(**self._params)
        try:
            logger.info("[FunctionCall] 大模型输出：%s",
                        response.choices[0].message.tool_calls[0].function.arguments)
            return response.choices[0].message.tool_calls[0].function.arguments
        except Exception:  # noqa: BLE001
            ans = response.choices[0].message.content
            logger.info("[FunctionCall] 大模型输出：%s", ans)
            return await FunctionLLM.process_response(ans)

    @staticmethod
    async def process_response(response: str) -> str:
        """处理大模型的输出"""
        # 去掉推理过程，避免干扰
        for token in REASONING_END_TOKEN:
            response = response.split(token)[-1]

        # 尝试解析JSON
        response = dedent(response).strip()
        error_flag = False
        try:
            json.loads(response)
        except Exception:  # noqa: BLE001
            error_flag = True

        if not error_flag:
            return response

        # 尝试提取```json中的JSON
        logger.warning("[FunctionCall] 直接解析失败！尝试提取```json中的JSON")
        try:
            json_str = re.findall(r"```json(.*)```", response, re.DOTALL)[-1]
            json_str = dedent(json_str).strip()
            json.loads(json_str)
        except Exception:  # noqa: BLE001
            # 尝试直接通过括号匹配JSON
            logger.warning("[FunctionCall] 提取失败！尝试正则提取JSON")
            try:
                json_str = re.findall(r"\{.*\}", response, re.DOTALL)[-1]
                json_str = dedent(json_str).strip()
                json.loads(json_str)
            except Exception:  # noqa: BLE001
                json_str = "{}"

        return json_str

    async def _call_ollama(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """
        调用ollama模型生成JSON

        :param list[dict[str, str]] messages: 历史消息列表
        :param dict[str, Any] schema: 输出JSON Schema
        :param int | None max_tokens: 最大Token长度
        :param float | None temperature: 大模型温度
        :return: 生成的对话回复
        :rtype: str
        """
        self._params.update({
            "messages": messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "format": schema,
        })

        # type: ignore[arg-type]
        response = await self._client.chat(**self._params)
        return await self.process_response(response.message.content or "")

    async def call(
        self,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """
        调用FunctionCall小模型

        不开放流式输出
        """
        # 检查max_tokens和temperature是否设置
        if max_tokens is None:
            max_tokens = self._config.max_tokens
        if temperature is None:
            temperature = self._config.temperature

        if self._config.backend == "ollama":
            json_str = await self._call_ollama(messages, schema, max_tokens, temperature)

        elif self._config.backend in ["function_call", "json_mode", "response_format", "vllm"]:
            json_str = await self._call_openai(messages, schema, max_tokens, temperature)

        else:
            err = "未知的Function模型后端"
            raise ValueError(err)

        try:
            return json.loads(json_str)
        except Exception:  # noqa: BLE001
            logger.error("[FunctionCall] 大模型JSON解析失败：%s", json_str)  # noqa: TRY400
            return {}


class JsonGenerator:
    """JSON生成器"""
    @staticmethod
    async def _parse_result_by_stack(result: str, schema: dict[str, Any]) -> str:
        """解析推理结果"""
        left_index = result.find('{')
        right_index = result.rfind('}')
        if left_index != -1 and right_index != -1 and left_index < right_index:
            try:
                tmp_js = json.loads(result[left_index:right_index + 1])
                validate(instance=tmp_js, schema=schema)
                return tmp_js
            except Exception as e:
                logger.error("[JsonGenerator] 解析结果失败: %s", e)
        stack = []
        json_candidates = []
        # 定义括号匹配关系
        bracket_map = {')': '(', ']': '[', '}': '{'}

        for i, char in enumerate(result):
            # 遇到左括号则入栈
            if char in bracket_map.values():
                stack.append((char, i))
            # 遇到右括号且栈不为空时检查匹配
            elif char in bracket_map.keys() and stack:
                if not stack:
                    continue
                top_char, top_index = stack[-1]
                # 检查是否匹配当前右括号
                if top_char == bracket_map[char]:
                    stack.pop()
                    # 当栈为空且当前是右花括号时，认为找到一个完整JSON
                    if not stack and char == '}':
                        json_str = result[top_index:i+1]
                        json_candidates.append(json_str)
                else:
                    # 如果不匹配，清空栈
                    stack.clear()
        # 移除重复项并保持顺序
        seen = set()
        unique_jsons = []
        for json_str in json_candidates[::]:
            if json_str not in seen:
                seen.add(json_str)
                unique_jsons.append(json_str)

        for json_str in unique_jsons:
            try:
                tmp_js = json.loads(json_str)
                validate(instance=tmp_js, schema=schema)
                return tmp_js
            except Exception as e:
                logger.error("[JsonGenerator] 解析结果失败: %s", e)
        return None

    def __init__(self, query: str, conversation: list[dict[str, str]], schema: dict[str, Any]) -> None:
        """初始化JSON生成器"""
        self._query = query
        self._conversation = conversation
        self._schema = schema

        self._trial = {}
        self._count = 0
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._err_info = ""

    async def _assemble_message(self) -> str:
        """组装消息"""
        # 检查类型
        function_call = Config().get_config().function_call.backend == "function_call"

        # 渲染模板
        template = self._env.from_string(JSON_GEN_BASIC)
        return template.render(
            query=self._query,
            conversation=self._conversation,
            previous_trial=self._trial,
            schema=self._schema,
            function_call=function_call,
            err_info=self._err_info,
        )

    async def _single_trial(self, max_tokens: int | None = None, temperature: float | None = None) -> dict[str, Any]:
        """单次尝试"""
        prompt = await self._assemble_message()
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "please generate a JSON response based on the above information and schema."},
        ]
        function = FunctionLLM()
        return await function.call(messages, self._schema, max_tokens, temperature)

    async def generate(self) -> dict[str, Any]:
        """生成JSON"""
        Draft7Validator.check_schema(self._schema)
        validator = Draft7Validator(self._schema)

        while self._count < JSON_GEN_MAX_TRIAL:
            self._count += 1
            result = await self._single_trial()
            try:
                validator.validate(result)
            except Exception as err:  # noqa: BLE001
                err_info = str(err)
                err_info = err_info.split("\n\n")[0]
                self._err_info = err_info
                logger.info("[JSONGenerator] 验证失败：%s", self._err_info)
                continue
            return result

        return {}
