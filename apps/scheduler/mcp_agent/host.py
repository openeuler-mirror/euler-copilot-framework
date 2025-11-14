# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP宿主"""

import logging
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.llm import json_generator
from apps.models import LanguageType, MCPTools
from apps.scheduler.mcp_agent.base import MCPBase
from apps.schemas.task import TaskData

_logger = logging.getLogger(__name__)
_env = SandboxedEnvironment(
    loader=BaseLoader,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)
_LLM_QUERY_FIX = {
    LanguageType.CHINESE: "请生成修复之后的工具参数",
    LanguageType.ENGLISH: "Please generate the tool parameters after repair",
}


class MCPHost(MCPBase):
    """MCP宿主服务"""

    async def fill_params(
        self,
        mcp_tool: MCPTools,
        task: TaskData,
        current_input: dict[str, Any],
        params: dict[str, Any] | None = None,
        params_description: str = "",
    ) -> dict[str, Any]:
        """生成工具参数"""
        llm_query = _LLM_QUERY_FIX[task.runtime.language]
        error_message = task.state.errorMessage if task.state else {}
        prompt = _env.from_string(await self._load_prompt("gen_params")).render(
            tool_name=mcp_tool.toolName,
            goal=task.runtime.userInput,
            current_goal=task.runtime.userInput,
            tool_description=mcp_tool.description,
            input_schema=mcp_tool.inputSchema,
            input_params=current_input,
            error_message=error_message,
            params=params,
            params_description=params_description,
        )

        # 组装OpenAI Function标准的Function结构
        function = {
            "name": mcp_tool.toolName,
            "description": mcp_tool.description,
            "parameters": mcp_tool.inputSchema,
        }

        return await json_generator.generate(
            function=function,
            conversation=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
                {"role": "user", "content": llm_query},
            ],
            prompt=prompt,
        )
