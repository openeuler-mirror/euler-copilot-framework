# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 用户目标拆解与规划"""

import logging
from copy import deepcopy
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.llm import json_generator
from apps.models import MCPTools
from apps.scheduler.slot.slot import Slot
from apps.schemas.mcp import (
    ToolRisk,
)

from .base import MCPBase
from .func import (
    EVALUATE_TOOL_RISK_FUNCTION,
    GET_MISSING_PARAMS_FUNCTION,
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

    async def get_missing_param(
        self, tool: MCPTools, input_param: dict[str, Any], error_message: dict[str, Any],
    ) -> dict[str, Any]:
        """获取缺失的参数"""
        slot = Slot(schema=tool.inputSchema)
        template = _env.from_string(await self._load_prompt("get_missing_params"))
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
            ],
            prompt=prompt,
        )
