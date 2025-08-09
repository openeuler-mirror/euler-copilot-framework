# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""选择MCP Server及其工具"""

import logging
import random
from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from typing import AsyncGenerator, Any

from apps.llm.function import JsonGenerator
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
    async def get_resoning_result(prompt: str, resoning_llm: ReasoningLLM = ReasoningLLM()) -> str:
        """获取推理结果"""
        # 调用推理大模型
        message = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
        result = ""
        async for chunk in resoning_llm.call(
            message,
            streaming=False,
            temperature=0.07,
            result_only=True,
        ):
            result += chunk

        return result

    @staticmethod
    async def _parse_result(result: str, schema: dict[str, Any]) -> str:
        """解析推理结果"""
        json_generator = JsonGenerator(
            result,
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "请提取下面内容中的json\n\n"+result},
            ],
            schema,
        )
        json_result = await json_generator.generate()
        return json_result

    @staticmethod
    async def select_top_tool(
            goal: str, tool_list: list[MCPTool],
            additional_info: str | None = None, top_n: int | None = None,
            reasoning_llm: ReasoningLLM | None = None) -> list[MCPTool]:
        """选择最合适的工具"""
        random.shuffle(tool_list)
        max_tokens = reasoning_llm._config.max_tokens
        template = _env.from_string(TOOL_SELECT)
        token_calculator = TokenCalculator()
        if token_calculator.calculate_token_length(
                messages=[{"role": "user", "content": template.render(
                    goal=goal, tools=[], additional_info=additional_info
                )}],
                pure_text=True) > max_tokens:
            logger.warning("[MCPSelector] 工具选择模板长度超过最大令牌数，无法进行选择")
            return []
        current_index = 0
        tool_ids = []
        while current_index < len(tool_list):
            index = current_index
            sub_tools = []
            while index < len(tool_list):
                tool = tool_list[index]
                tokens = token_calculator.calculate_token_length(
                    messages=[{"role": "user", "content": template.render(
                        goal=goal, tools=[tool],
                        additional_info=additional_info
                    )}],
                    pure_text=True
                )
                if tokens > max_tokens:
                    continue
                sub_tools.append(tool)

                tokens = token_calculator.calculate_token_length(messages=[{"role": "user", "content": template.render(
                    goal=goal, tools=sub_tools, additional_info=additional_info)}, ], pure_text=True)
                if tokens > max_tokens:
                    del sub_tools[-1]
                    break
                else:
                    index += 1
            current_index = index
            if sub_tools:
                schema = MCPToolIdsSelectResult.model_json_schema()
                if "items" not in schema["properties"]["tool_ids"]:
                    schema["properties"]["tool_ids"]["items"] = {}
                # 将enum添加到items中，限制数组元素的可选值
                schema["properties"]["tool_ids"]["items"]["enum"] = [tool.id for tool in sub_tools]
                result = await MCPSelector.get_resoning_result(template.render(goal=goal, tools=sub_tools, additional_info="请根据目标选择对应的工具"), reasoning_llm)
                result = await MCPSelector._parse_result(result, schema)
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
