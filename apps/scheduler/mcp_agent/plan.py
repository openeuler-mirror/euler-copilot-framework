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
    GET_FLOW_NAME_FUNCTION,
    GET_MISSING_PARAMS,
    IS_PARAM_ERROR_FUNCTION,
)
from apps.scheduler.slot.slot import Slot
from apps.schemas.llm import LLMChunk
from apps.schemas.mcp import (
    FlowName,
    IsParamError,
    Step,
    ToolRisk,
)
from apps.schemas.task import TaskData

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
        template = _env.from_string(await self._load_prompt("gen_agent_name"))
        prompt = template.render(goal=self._goal)

        result = await json_generator.generate(
            function=GET_FLOW_NAME_FUNCTION[self._language],
            conversation=[
                {"role": "system", "content": "You are a helpful assistant."},
            ],
            prompt=prompt,
        )
        return FlowName.model_validate(result)

    async def create_next_step(self, tools: list[MCPTools], task: TaskData) -> Step:
        """创建下一步的执行步骤"""
        template = _env.from_string(await self._load_prompt("gen_step"))
        prompt = template.render(goal=self._goal, tools=tools)

        function = deepcopy(CREATE_NEXT_STEP_FUNCTION[self._language])
        function["parameters"]["properties"]["tool_name"]["enum"] = [tool.toolName for tool in tools]

        history = await self.assemble_memory(task)

        step = await json_generator.generate(
            function=function,
            conversation=[
                {"role": "system", "content": "You are a helpful assistant."},
                *history,
            ],
            prompt=prompt,
        )
        logger.info("[MCPPlanner] 创建下一步的执行步骤: %s", step)
        return Step.model_validate(step)

    async def get_tool_risk(
        self,
        tool: MCPTools,
        input_param: dict[str, Any],
    ) -> ToolRisk:
        """获取MCP工具的风险评估结果"""
        template = _env.from_string(await self._load_prompt("risk_evaluate"))
        prompt = template.render(
            tool_name=tool.toolName,
            tool_description=tool.description,
            input_param=input_param,
        )

        risk = await json_generator.generate(
            function=EVALUATE_TOOL_RISK_FUNCTION[self._language],
            conversation=[
                {"role": "system", "content": "You are a helpful assistant."},
            ],
            prompt=prompt,
        )

        return ToolRisk.model_validate(risk)

    async def is_param_error(
        self,
        task: TaskData,
        error_message: str,
        tool: MCPTools,
        step_goal: str,
        input_params: dict[str, Any],
    ) -> IsParamError:
        """判断错误信息是否是参数错误"""
        tmplate = _env.from_string(await self._load_prompt("is_param_error"))
        prompt = tmplate.render(
            goal=self._goal,
            step_id=tool.toolName,
            step_name=tool.toolName,
            step_goal=step_goal,
            input_params=input_params,
            error_message=error_message,
        )
        history = await self.assemble_memory(task)

        is_param_error = await json_generator.generate(
            function=IS_PARAM_ERROR_FUNCTION[self._language],
            conversation=[
                {"role": "system", "content": "You are a helpful assistant."},
                *history,
            ],
            prompt=prompt,
        )
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

        function = deepcopy(GET_MISSING_PARAMS_FUNCTION[self._language])
        function["parameters"] = schema_with_null

        return await json_generator.generate(
            function=function,
            conversation=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            language=self._language,
        )

    async def generate_answer(self, task: TaskData, llm: LLM) -> AsyncGenerator[LLMChunk, None]:
        """生成最终回答,返回LLMChunk"""
        template = _env.from_string(FINAL_ANSWER[self._language])
        prompt = template.render(
            goal=self._goal,
        )

        history = await self.assemble_memory(task)
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            *history,
            {"role": "user", "content": prompt},
        ]

        async for chunk in llm.call(
            messages,
            streaming=True,
        ):
            yield chunk
