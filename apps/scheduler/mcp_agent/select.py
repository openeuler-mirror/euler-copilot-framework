# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""选择MCP Server及其工具"""

import logging
import random
from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from typing import AsyncGenerator

from apps.llm.reasoning import ReasoningLLM
from apps.common.lance import LanceDB
from apps.common.mongo import MongoDB
from apps.llm.embedding import Embedding
from apps.llm.function import FunctionLLM
from apps.llm.reasoning import ReasoningLLM
from apps.llm.token import TokenCalculator
from apps.scheduler.mcp_agent.prompt import TOOL_SELECT
from apps.schemas.mcp import (
    BaseModel,
    MCPCollection,
    MCPSelectResult,
    MCPTool,
    MCPToolIdsSelectResult
)
from apps.common.config import Config
logger = logging.getLogger(__name__)

_env = SandboxedEnvironment(
    loader=BaseLoader,
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

FINAL_TOOL_ID = "FIANL"
SUMMARIZE_TOOL_ID = "SUMMARIZE"


class MCPSelector:
    """MCP选择器"""

    @staticmethod
    async def select_top_tool(
            goal: str, tool_list: list[MCPTool],
            additional_info: str | None = None, top_n: int | None = None) -> list[MCPTool]:
        """选择最合适的工具"""
        random.shuffle(tool_list)
        max_tokens = Config().get_config().function_call.max_tokens
        template = _env.from_string(TOOL_SELECT)
        if TokenCalculator.calculate_token_length(
                messages=[{"role": "user", "content": template.render(
                    goal=goal, tools=[], additional_info=additional_info
                )}],
                pure_text=True) > max_tokens:
            logger.warning("[MCPSelector] 工具选择模板长度超过最大令牌数，无法进行选择")
            return []
        llm = FunctionLLM()
        current_index = 0
        tool_ids = []
        while current_index < len(tool_list):
            index = current_index
            sub_tools = []
            while index < len(tool_list):
                tool = tool_list[index]
                tokens = TokenCalculator.calculate_token_length(
                    messages=[{"role": "user", "content": template.render(
                        goal=goal, tools=[tool],
                        additional_info=additional_info
                    )}],
                    pure_text=True
                )
                if tokens > max_tokens:
                    continue
                sub_tools.append(tool)

                tokens = TokenCalculator.calculate_token_length(messages=[{"role": "user", "content": template.render(
                    goal=goal, tools=sub_tools, additional_info=additional_info)}, ], pure_text=True)
                if tokens > max_tokens:
                    del sub_tools[-1]
                    break
                else:
                    index += 1
            current_index = index
            if sub_tools:
                message = [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": template.render(tools=sub_tools)},
                ]
                schema = MCPToolIdsSelectResult.model_json_schema()
                schema["properties"]["tool_ids"]["enum"] = [tool.id for tool in sub_tools]
                result = await llm.call(messages=message, schema=schema)
                try:
                    result = MCPToolIdsSelectResult.model_validate(result)
                    tool_ids.extend(result.tool_ids)
                except Exception:
                    logger.exception("[MCPSelector] 解析MCP工具ID选择结果失败")
                    continue
        mcp_tools = [tool for tool in tool_list if tool.id in tool_ids]

        if top_n is not None:
            mcp_tools = mcp_tools[:top_n]
        mcp_tools.append(MCPTool(id=FINAL_TOOL_ID, name="Final",
                         description="终止", mcp_id=FINAL_TOOL_ID, input_schema={}))
        # mcp_tools.append(MCPTool(id=SUMMARIZE_TOOL_ID, name="Summarize",
        #                  description="总结工具", mcp_id=SUMMARIZE_TOOL_ID, input_schema={}))
        return mcp_tools
