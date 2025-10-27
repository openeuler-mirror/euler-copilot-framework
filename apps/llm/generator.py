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
from .prompt import JSON_GEN_BASIC, JSON_NO_FUNCTION_CALL

_logger = logging.getLogger(__name__)

JSON_GEN_MAX_TRIAL = 3

class JsonGenerator:
    """综合Json生成器（全局单例）"""

    def __init__(self, llm: LLM | None = None) -> None:
        """创建JsonGenerator实例"""
        # Jinja2环境，可以复用
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            extensions=["jinja2.ext.loopcontrols"],
        )
        # 初始化时设为None，调用init后设置
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

    async def _single_trial(
        self,
        function: dict[str, Any],
        query: str,
        context: list[dict[str, str]],
    ) -> dict[str, Any]:
        """单次尝试，包含校验逻辑；function使用OpenAI标准Function格式"""
        if self._llm is None:
            err = "[JSONGenerator] 未初始化，请先调用init()方法"
            raise RuntimeError(err)

        schema = function["parameters"]
        validator = Draft7Validator(schema)

        # 执行生成
        if self._support_function_call:
            # 如果支持FunctionCall
            result = await self._call_with_function(function, query, context)
        else:
            # 如果不支持FunctionCall
            result = await self._call_without_function(function, query, context)

        # 校验结果
        try:
            validator.validate(result)
        except Exception as err:
            err_info = str(err)
            err_info = err_info.split("\n\n")[0]
            _logger.info("[JSONGenerator] 验证失败：%s", err_info)

            context.append({
                "role": "assistant",
                "content": f"Attempted to use tool but validation failed: {err_info}",
            })
            raise
        else:
            return result

    async def _call_with_function(
        self,
        function: dict[str, Any],
        query: str,
        context: list[dict[str, str]],
    ) -> dict[str, Any]:
        """使用FunctionCall方式调用"""
        if self._llm is None:
            err = "[JSONGenerator] 未初始化，请先调用init()方法"
            raise RuntimeError(err)

        tool = LLMFunctions(
            name=function["name"],
            description=function["description"],
            param_schema=function["parameters"],
        )

        messages = context.copy()
        messages.append({"role": "user", "content": query})

        tool_call_result = {}
        async for chunk in self._llm.call(messages, include_thinking=False, streaming=True, tools=[tool]):
            if chunk.tool_call:
                tool_call_result.update(chunk.tool_call)

        function_name = function["name"]
        if tool_call_result and function_name in tool_call_result:
            return json.loads(tool_call_result[function_name])

        return {}

    async def _call_without_function(
        self,
        function: dict[str, Any],
        query: str,
        context: list[dict[str, str]],
    ) -> dict[str, Any]:
        """不使用FunctionCall方式调用"""
        if self._llm is None:
            err = "[JSONGenerator] 未初始化，请先调用init()方法"
            raise RuntimeError(err)

        template = self._env.from_string(JSON_GEN_BASIC + "\n\n" + JSON_NO_FUNCTION_CALL)
        prompt = template.render(
            query=query,
            conversation=context[1:] if context else [],
            schema=function["parameters"],
        )

        messages = [
            context[0],
            {"role": "user", "content": prompt},
        ]

        # 使用LLM的call方法获取响应
        full_response = ""
        async for chunk in self._llm.call(messages, include_thinking=False, streaming=True):
            if chunk.content:
                full_response += chunk.content

        # 从响应中提取JSON
        # 查找第一个 { 和最后一个 }
        json_match = re.search(r"\{.*\}", full_response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))

        return {}


    async def generate(
        self,
        query: str,
        function: dict[str, Any],
        conversation: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """
        生成JSON；function使用OpenAI标准Function格式

        Args:
            query: 用户查询
            function: OpenAI标准Function格式的函数定义
            conversation: 对话历史，默认为空列表

        Returns:
            生成的JSON对象

        """
        if self._llm is None:
            err = "[JSONGenerator] 未初始化，请先调用init()方法"
            raise RuntimeError(err)

        # 检查schema格式是否正确
        schema = function["parameters"]
        Draft7Validator.check_schema(schema)

        # 构建上下文
        context = [
            {
                "role": "system",
                "content": "You are a helpful assistant that can use tools to help answer user queries.",
            },
        ]
        if conversation:
            context.extend(conversation)

        count = 0
        original_context = context.copy()
        while count < JSON_GEN_MAX_TRIAL:
            count += 1
            try:
                # 如果_single_trial没有抛出异常，直接返回结果，不进行重试
                return await self._single_trial(function, query, context)
            except Exception:
                _logger.exception(
                    "[JSONGenerator] 第 %d/%d 次尝试失败",
                    count,
                    JSON_GEN_MAX_TRIAL,
                )
                if count < JSON_GEN_MAX_TRIAL:
                    continue
                context = original_context
        return {}


# 全局单例实例
json_generator = JsonGenerator()
