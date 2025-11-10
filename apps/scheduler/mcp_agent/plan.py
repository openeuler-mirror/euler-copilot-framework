# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 用户目标拆解与规划"""

import logging
from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.llm import LLM, json_generator
from apps.models import MCPTools
from apps.scheduler.mcp_agent.base import MCPBase
from apps.scheduler.mcp_agent.prompt import (
    CREATE_NEXT_STEP_FUNCTION,
    EVALUATE_TOOL_RISK_FUNCTION,
    FINAL_ANSWER,
    GEN_STEP,
    GENERATE_FLOW_NAME,
    GET_FLOW_NAME_FUNCTION,
    GET_MISSING_PARAMS,
    GET_MISSING_PARAMS_FUNCTION,
    IS_PARAM_ERROR,
    IS_PARAM_ERROR_FUNCTION,
    RISK_EVALUATE,
)
from apps.scheduler.slot.slot import Slot
from apps.schemas.llm import LLMChunk
from apps.schemas.mcp import (
    FlowName,
    IsParamError,
    Step,
    ToolRisk,
)

_env = SandboxedEnvironment(
    loader=BaseLoader,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)
logger = logging.getLogger(__name__)


class MCPPlanner(MCPBase):
    """MCP 用户目标拆解与规划"""

    async def get_flow_name(self) -> FlowName:
        """获取当前流程的名称"""
        template = _env.from_string(GENERATE_FLOW_NAME[self._language])
        prompt = template.render(goal=self.task.runtime.userInput)

        result = await json_generator.generate(
            function=GET_FLOW_NAME_FUNCTION[self._language],
            conversation=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            language=self._language,
        )
        return FlowName.model_validate(result)

    async def create_next_step(self, history: str, tools: list[MCPTools]) -> Step:
        """创建下一步的执行步骤"""
        # 构建提示词
        template = _env.from_string(GEN_STEP[self._language])
        prompt = template.render(goal=self.task.runtime.userInput, history=history, tools=tools)

        # 获取函数定义并动态设置tool_id的enum
        function = deepcopy(CREATE_NEXT_STEP_FUNCTION[self._language])
        function["parameters"]["properties"]["tool_name"]["enum"] = [tool.toolName for tool in tools]

        step = await json_generator.generate(
            function=function,
            conversation=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            language=self._language,
        )
        logger.info("[MCPPlanner] 创建下一步的执行步骤: %s", step)
        # 使用Step模型解析结果
        return Step.model_validate(step)

    async def get_tool_risk(
        self,
        tool: MCPTools,
        input_param: dict[str, Any],
        additional_info: str = "",
    ) -> ToolRisk:
        """获取MCP工具的风险评估结果"""
        # 构建提示词
        template = _env.from_string(RISK_EVALUATE[self._language])
        prompt = template.render(
            tool_name=tool.toolName,
            tool_description=tool.description,
            input_param=input_param,
            additional_info=additional_info,
        )

        risk = await json_generator.generate(
            function=EVALUATE_TOOL_RISK_FUNCTION[self._language],
            conversation=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            language=self._language,
        )

        # 返回风险评估结果
        return ToolRisk.model_validate(risk)

    async def is_param_error(
        self,
        history: str,
        error_message: str,
        tool: MCPTools,
        step_description: str,
        input_params: dict[str, Any],
    ) -> IsParamError:
        """判断错误信息是否是参数错误"""
        tmplate = _env.from_string(IS_PARAM_ERROR[self._language])
        prompt = tmplate.render(
            goal=self.task.runtime.userInput,
            history=history,
            step_id=tool.toolName,
            step_name=tool.toolName,
            step_description=step_description,
            input_params=input_params,
            error_message=error_message,
        )

        is_param_error = await json_generator.generate(
            function=IS_PARAM_ERROR_FUNCTION[self._language],
            conversation=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            language=self._language,
        )
        # 使用IsParamError模型解析结果
        return IsParamError.model_validate(is_param_error)

    async def get_missing_param(
        self, tool: MCPTools, input_param: dict[str, Any], error_message: dict[str, Any],
    ) -> dict[str, Any]:
        """获取缺失的参数"""
        slot = Slot(schema=tool.inputSchema)
        template = _env.from_string(GET_MISSING_PARAMS[self._language])
        schema_with_null = slot.add_null_to_basic_types()
        prompt = template.render(
            tool_name=tool.toolName,
            tool_description=tool.description,
            input_param=input_param,
            schema=schema_with_null,
            error_message=error_message,
        )

        # 获取函数定义并设置parameters为schema_with_null
        function = deepcopy(GET_MISSING_PARAMS_FUNCTION[self._language])
        function["parameters"] = schema_with_null

        # 解析为结构化数据
        return await json_generator.generate(
            function=function,
            conversation=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            language=self._language,
        )

    async def generate_answer(self, memory: str, llm: LLM) -> AsyncGenerator[LLMChunk, None]:
        """生成最终回答，返回LLMChunk"""
        template = _env.from_string(FINAL_ANSWER[self._language])
        prompt = template.render(
            memory=memory,
            goal=self.task.runtime.userInput,
        )
        async for chunk in llm.call(
            [{"role": "user", "content": prompt}],
            streaming=True,
        ):
            yield chunk
