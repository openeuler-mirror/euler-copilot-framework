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
from apps.schemas.scheduler import LLMConfig

from .llm import LLM
from .prompt import JSON_GEN_BASIC, JSON_NO_FUNCTION_CALL

_logger = logging.getLogger(__name__)

JSON_GEN_MAX_TRIAL = 3  # 最大尝试次数

class JsonGenerator:
    """综合Json生成器"""

    def __init__(
        self, llm_config: LLMConfig, query: str, conversation: list[dict[str, str]], function: dict[str, Any],
    ) -> None:
        """初始化JSON生成器；function使用OpenAI标准Function格式"""
        self._query = query
        self._function = function

        # 选择LLM：优先使用Function模型（如果存在且支持FunctionCall），否则回退到Reasoning模型
        self._llm, self._support_function_call = self._select_llm(llm_config)

        self._context = [
            {
                "role": "system",
                "content": "You are a helpful assistant that can use tools to help answer user queries.",
            },
        ]
        if conversation:
            self._context.extend(conversation)

        self._count = 0
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            extensions=["jinja2.ext.loopcontrols"],
        )

    def _select_llm(self, llm_config: LLMConfig) -> tuple[LLM, bool]:
        """选择LLM：优先使用Function模型（如果存在且支持FunctionCall），否则回退到Reasoning模型"""
        if llm_config.function is not None and LLMType.FUNCTION in llm_config.function.config.llmType:
            _logger.info("[JSONGenerator] 使用Function模型，支持FunctionCall")
            return llm_config.function, True

        _logger.info("[JSONGenerator] Function模型不可用或不支持FunctionCall，回退到Reasoning模型")
        return llm_config.reasoning, False

    async def _single_trial(self, max_tokens: int | None = None, temperature: float | None = None) -> dict[str, Any]:
        """单次尝试，包含校验逻辑"""
        # 获取schema并创建验证器
        schema = self._function["parameters"]
        validator = Draft7Validator(schema)

        # 执行生成
        if self._support_function_call:
            # 如果支持FunctionCall，使用provider的function调用逻辑
            result = await self._call_with_function()
        else:
            # 如果不支持FunctionCall，使用JSON_GEN_BASIC和provider的call进行调用
            result = await self._call_without_function(max_tokens, temperature)

        # 校验结果
        try:
            validator.validate(result)
        except Exception as err:
            # 捕获校验异常信息
            err_info = str(err)
            err_info = err_info.split("\n\n")[0]
            _logger.info("[JSONGenerator] 验证失败：%s", err_info)

            # 将错误信息添加到上下文中
            self._context.append({
                "role": "assistant",
                "content": f"Attempted to use tool but validation failed: {err_info}",
            })
            raise
        else:
            return result

    async def _call_with_function(self) -> dict[str, Any]:
        """使用FunctionCall方式调用"""
        # 直接使用传入的function构建工具定义
        tool = LLMFunctions(
            name=self._function["name"],
            description=self._function["description"],
            param_schema=self._function["parameters"],
        )

        messages = self._context.copy()
        messages.append({"role": "user", "content": self._query})

        # 调用LLM的call方法，传入tools
        tool_call_result = {}
        async for chunk in self._llm.call(messages, include_thinking=False, streaming=True, tools=[tool]):
            if chunk.tool_call:
                tool_call_result.update(chunk.tool_call)

        # 从tool_call结果中提取JSON，使用function中的函数名
        function_name = self._function["name"]
        if tool_call_result and function_name in tool_call_result:
            return json.loads(tool_call_result[function_name])

        return {}

    async def _call_without_function(self, max_tokens: int | None = None, temperature: float | None = None) -> dict[str, Any]:  # noqa: E501
        """不使用FunctionCall方式调用"""
        # 渲染模板
        template = self._env.from_string(JSON_GEN_BASIC + "\n\n" + JSON_NO_FUNCTION_CALL)
        prompt = template.render(
            query=self._query,
            conversation=self._context[1:] if self._context else [],
            schema=self._function["parameters"],
        )

        messages = [
            self._context[0],
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


    async def generate(self) -> dict[str, Any]:
        """生成JSON"""
        # 检查schema格式是否正确
        schema = self._function["parameters"]
        Draft7Validator.check_schema(schema)

        while self._count < JSON_GEN_MAX_TRIAL:
            self._count += 1
            try:
                return await self._single_trial()
            except Exception:  # noqa: BLE001
                # 校验失败，_single_trial已经将错误信息记录到self._err_info中并记录日志
                continue

        return {}
