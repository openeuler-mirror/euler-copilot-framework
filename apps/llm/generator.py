# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""综合Json生成器"""

import json
import logging
import re
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from jsonschema import Draft7Validator

from apps.models import LLMType
from apps.schemas.llm import LLMFunctions

from .llm import LLM
from .token import token_calculator

_logger = logging.getLogger(__name__)

JSON_GEN_MAX_TRIAL = 3


class JsonValidationError(Exception):
    """JSON验证失败异常，携带生成的结果"""

    def __init__(self, message: str, result: dict[str, Any]) -> None:
        """初始化异常"""
        super().__init__(message)
        self.result = result


class JsonGenerator:
    """综合Json生成器（全局单例）"""

    def __init__(self, llm: LLM | None = None) -> None:
        """创建JsonGenerator实例"""
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            extensions=["jinja2.ext.loopcontrols"],
        )
        self._llm: LLM | None = llm
        self._support_function_call: bool = False
        if llm is not None:
            self._check_function_call_support()

    def init(self, llm: LLM) -> None:
        """初始化JsonGenerator，设置LLM配置"""
        self._llm = llm
        self._check_function_call_support()

    def _check_function_call_support(self) -> None:
        """检查LLM是否支持FunctionCall"""
        if self._llm is not None and LLMType.FUNCTION in self._llm.config.llmType:
            _logger.info("[JSONGenerator] LLM支持FunctionCall")
            self._support_function_call = True
        else:
            _logger.info("[JSONGenerator] LLM不支持FunctionCall，将使用prompt方式")
            self._support_function_call = False

    def _build_messages(
        self,
        prompt: str,
        conversation: list[dict[str, str]],
        retry_messages: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        """构建messages，拼接顺序：真实对话记录 - Prompt - 重试记录"""
        messages = [*conversation, {"role": "user", "content": prompt}]

        if self._llm is not None:
            token_count = token_calculator.calculate_token_length(messages)
            retry_token_count = token_calculator.calculate_token_length(retry_messages) if retry_messages else 0
            ctx_length = self._llm.config.ctxLength

            available_ctx = ctx_length - retry_token_count

            if token_count > available_ctx:
                _logger.warning(
                    "[JSONGenerator] 当前对话 Token 数量 (%d) 超过可用上下文长度 (%d)，"
                    "进行消息裁剪（重试记录 Token: %d）",
                    token_count,
                    available_ctx,
                    retry_token_count,
                )

                while len(messages) > 1 and token_count > available_ctx:
                    deleted = False
                    for i, msg in enumerate(messages):
                        if msg["role"] in ("user", "assistant"):
                            messages = messages[:i] + messages[i + 1:]
                            deleted = True
                            break

                    if not deleted:
                        err = (
                            f"[JSONGenerator] 无法裁剪消息以满足上下文长度限制，"
                            f"当前 Token 数量: {token_count}，可用上下文长度: {available_ctx}"
                        )
                        raise RuntimeError(err)

                    token_count = token_calculator.calculate_token_length(messages)

                _logger.info(
                    "[JSONGenerator] 裁剪后对话 Token 数量: %d（重试记录 Token: %d，总计: %d）",
                    token_count,
                    retry_token_count,
                    token_count + retry_token_count,
                )

        messages.extend(retry_messages or [])
        return messages

    async def _single_trial(
        self,
        function: dict[str, Any],
        prompt: str,
        conversation: list[dict[str, str]],
        retry_messages: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """单次尝试，包含校验逻辑；function使用OpenAI标准Function格式"""
        if self._llm is None:
            err = "[JSONGenerator] 未初始化，请先调用init()方法"
            raise RuntimeError(err)

        schema = function["parameters"]
        validator = Draft7Validator(schema)

        if self._support_function_call:
            use_xml_format = False
            template = self._env.from_string(prompt)
            formatted_prompt = template.render(use_xml_format=use_xml_format)
            result = await self._call_with_function(function, formatted_prompt, conversation, retry_messages)
        else:
            use_xml_format = True
            template = self._env.from_string(prompt)
            formatted_prompt = template.render(use_xml_format=use_xml_format)
            result = await self._call_without_function(function, formatted_prompt, conversation, retry_messages)

        try:
            validator.validate(result)
        except Exception as err:
            err_info = str(err)
            err_info = err_info.split("\n\n")[0]
            _logger.info("[JSONGenerator] 验证失败：%s", err_info)

            validation_error = JsonValidationError(err_info, result)
            raise validation_error from err
        else:
            return result

    async def _call_with_function(
        self,
        function: dict[str, Any],
        prompt: str,
        conversation: list[dict[str, str]],
        retry_messages: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """使用FunctionCall方式调用"""
        if self._llm is None:
            err = "[JSONGenerator] 未初始化，请先调用init()方法"
            raise RuntimeError(err)

        messages = self._build_messages(prompt, conversation, retry_messages)

        tool = LLMFunctions(
            name=function["name"],
            description=function["description"],
            param_schema=function["parameters"],
        )

        tool_call_result = {}
        async for chunk in self._llm.call(messages, include_thinking=False, streaming=False, tools=[tool]):
            if chunk.tool_call:
                tool_call_result.update(chunk.tool_call)

        function_name = function["name"]
        if tool_call_result and function_name in tool_call_result:
            return json.loads(tool_call_result[function_name])

        return {}

    async def _call_without_function(
        self,
        _function: dict[str, Any],
        prompt: str,
        conversation: list[dict[str, str]],
        retry_messages: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """不使用FunctionCall方式调用"""
        if self._llm is None:
            err = "[JSONGenerator] 未初始化，请先调用init()方法"
            raise RuntimeError(err)

        messages = self._build_messages(prompt, conversation, retry_messages)

        full_response = ""
        async for chunk in self._llm.call(messages, include_thinking=False, streaming=False):
            if chunk.content:
                full_response += chunk.content

        json_match = re.search(r"\{.*\}", full_response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))

        return {}


    async def generate(
        self,
        function: dict[str, Any],
        prompt: str,
        conversation: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """生成JSON；function使用OpenAI标准Function格式"""
        if self._llm is None:
            err = "[JSONGenerator] 未初始化，请先调用init()方法"
            raise RuntimeError(err)

        schema = function["parameters"]
        Draft7Validator.check_schema(schema)

        count = 0

        retry_messages: list[dict[str, str]] = []
        if conversation is None:
            conversation = []

        while count < JSON_GEN_MAX_TRIAL:
            count += 1
            try:
                return await self._single_trial(function, prompt, conversation, retry_messages)
            except (JsonValidationError, json.JSONDecodeError) as e:
                _logger.exception(
                    "[JSONGenerator] 第 %d/%d 次尝试失败",
                    count,
                    JSON_GEN_MAX_TRIAL,
                )
                if count < JSON_GEN_MAX_TRIAL:
                    err_info = str(e)
                    err_info = err_info.split("\n\n")[0]

                    function_name = function["name"]
                    result_json = json.dumps(err_info, ensure_ascii=False)

                    retry_messages.append({
                        "role": "assistant",
                        "content": f"I called function {function_name} with parameters: {result_json}",
                    })

                    retry_messages.append({
                        "role": "user",
                        "content": (
                            f"The previous function call failed with validation error: {err_info}. "
                            "Please try again and ensure the output strictly follows the required schema."
                        ),
                    })
                    continue
            except Exception:
                _logger.exception(
                    "[JSONGenerator] 第 %d/%d 次尝试失败（非验证错误）",
                    count,
                    JSON_GEN_MAX_TRIAL,
                )
                if count < JSON_GEN_MAX_TRIAL:
                    continue
        return {}


json_generator = JsonGenerator()
