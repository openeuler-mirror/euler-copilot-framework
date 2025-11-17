# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""选择MCP Server及其工具"""

import copy
import logging

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy import select

from apps.common.postgres import postgres
from apps.llm import LLM, embedding, json_generator
from apps.models import LanguageType, MCPTools
from apps.schemas.mcp import MCPSelectResult
from apps.services.mcp_service import MCPServiceManager

from .base import MCPNodeBase
from .prompt import SELECT_MCP_FUNCTION

logger = logging.getLogger(__name__)


class MCPSelector(MCPNodeBase):
    """MCP选择器"""

    def __init__(self, llm: LLM, language: LanguageType = LanguageType.CHINESE) -> None:
        """初始化MCP选择器"""
        super().__init__(llm, language)
        self._env = SandboxedEnvironment(
            loader=BaseLoader,
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    async def _call_reasoning(self, prompt: str) -> str:
        """调用大模型进行推理"""
        logger.info("[MCPSelector] 调用推理大模型")
        message = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
        result = ""
        async for chunk in self._llm.call(message):
            result += chunk.content or ""
        return result


    async def _call_function_mcp(self, reasoning_result: str, mcp_ids: list[str]) -> MCPSelectResult:
        """调用结构化输出小模型提取JSON"""
        function = copy.deepcopy(SELECT_MCP_FUNCTION[self._language])
        function["parameters"]["properties"]["mcp_id"]["enum"] = mcp_ids

        # 使用jinja2格式化模板
        template = self._env.from_string(await self._load_prompt("mcp_select"))
        user_prompt = template.render(
            reasoning_result=reasoning_result,
            mcp_ids=mcp_ids,
        )

        # 使用json_generator生成JSON
        result = await json_generator.generate(
            function=function,
            conversation=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_prompt},
            ],
            language=self._language,
        )

        try:
            result = MCPSelectResult.model_validate(result)
        except Exception:
            logger.exception("[MCPSelector] 解析MCP Select Result失败")
            raise
        return result


    async def select_top_tool(self, query: str, mcp_list: list[str], top_n: int = 10) -> list[MCPTools]:
        """选择最合适的工具"""
        query_embedding = await embedding.get_embedding([query])
        async with postgres.session() as session:
            tool_vecs = await session.scalars(
                select(embedding.MCPToolVector).where(embedding.MCPToolVector.mcpId.in_(mcp_list))
                .order_by(embedding.MCPToolVector.embedding.cosine_distance(query_embedding)).limit(top_n),
            )

        # 拿到工具
        llm_tool_list = []

        for tool_vec in tool_vecs:
            logger.info("[MCPHelper] 查询MCP Tool名称和描述: %s", tool_vec.mcpId)
            tool_data = await MCPServiceManager.get_mcp_tools(tool_vec.mcpId)
            llm_tool_list.extend(tool_data)

        return llm_tool_list
