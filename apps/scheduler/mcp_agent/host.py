# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP宿主"""

import json
import logging
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from mcp.types import TextContent

from apps.common.mongo import MongoDB
from apps.llm.function import JsonGenerator
from apps.scheduler.mcp.prompt import MEMORY_TEMPLATE
from apps.scheduler.pool.mcp.client import MCPClient
from apps.scheduler.pool.mcp.pool import MCPPool
from apps.scheduler.mcp_agent.prompt import REPAIR_PARAMS
from apps.schemas.enum_var import StepStatus
from apps.schemas.mcp import MCPPlanItem, MCPTool
from apps.schemas.task import Task, FlowStepHistory
from apps.services.task import TaskManager

logger = logging.getLogger(__name__)

_env = SandboxedEnvironment(
    loader=BaseLoader,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def tojson_filter(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


_env.filters['tojson'] = tojson_filter


class MCPHost:
    """MCP宿主服务"""

    @staticmethod
    async def assemble_memory(task: Task) -> str:
        """组装记忆"""

        return _env.from_string(MEMORY_TEMPLATE).render(
            context_list=task.context,
        )

    async def _get_first_input_params(mcp_tool: MCPTool, query: str, task: Task) -> dict[str, Any]:
        """填充工具参数"""
        # 更清晰的输入·指令，这样可以调用generate
        llm_query = rf"""
            请使用参数生成工具，生成满足以下目标的工具参数：

            {query}
        """

        # 进行生成
        json_generator = JsonGenerator(
            llm_query,
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": await MCPHost.assemble_memory(task)},
            ],
            mcp_tool.input_schema,
        )
        return await json_generator.generate()

    async def _fill_params(mcp_tool: MCPTool,
                           goal: str,
                           current_input: dict[str, Any],
                           error_message: str = "", params: dict[str, Any] = {},
                           params_description: str = "") -> dict[str, Any]:
        llm_query = "请生成修复之后的工具参数"
        prompt = _env.from_string(REPAIR_PARAMS).render(
            tool_name=mcp_tool.name,
            gaol=goal,
            tool_description=mcp_tool.description,
            input_schema=mcp_tool.input_schema,
            current_input=current_input,
            error_message=error_message,
            params=params,
            params_description=params_description,
        )

        json_generator = JsonGenerator(
            llm_query,
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            mcp_tool.input_schema,
        )
        return await json_generator.generate()
