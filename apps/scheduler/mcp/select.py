# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""选择MCP Server及其工具"""

import logging

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.common.postgres import DataBase
from apps.common.mongo import MongoDB
from apps.llm.embedding import Embedding
from apps.llm.function import FunctionLLM
from apps.llm.reasoning import ReasoningLLM
from apps.services.vector import VectorManager
from apps.scheduler.mcp.prompt import (
    MCP_SELECT,
)
from apps.schemas.enum_var import LanguageType
from apps.schemas.mcp import (
    MCPCollection,
    MCPSelectResult,
    MCPTool,
)

logger = logging.getLogger(__name__)


class MCPSelector:
    """MCP选择器"""

    def __init__(self) -> None:
        """初始化助手类"""
        self.input_tokens = 0
        self.output_tokens = 0

    @staticmethod
    async def select_top_tool(
        query: str, mcp_list: list[str], top_n: int = 10
    ) -> list[MCPTool]:
        """选择最合适的工具"""
        query_embedding = await Embedding.get_embedding([query])
        tool_vecs = await VectorManager.select_topk_mcp_tool_by_mcp_ids(
            vector=query_embedding[0],
            mcp_ids=mcp_list,
            top_k=top_n,
        )

        # 拿到工具
        tool_collection = MongoDB().get_collection("mcp")
        llm_tool_list = []

        for tool_vec in tool_vecs:
            # 到MongoDB里找对应的工具
            logger.info("[MCPHelper] 查询MCP Tool名称和描述: %s", tool_vec.mcp_id)
            tool_data = await tool_collection.aggregate([
                {"$match": {"_id": tool_vec.mcp_id}},
                {"$unwind": "$tools"},
                {"$match": {"tools.id": tool_vec.id}},
                {"$project": {"_id": 0, "tools": 1}},
                {"$replaceRoot": {"newRoot": "$tools"}},
            ])
            async for tool in tool_data:
                tool_obj = MCPTool.model_validate(tool)
                llm_tool_list.append(tool_obj)

        return llm_tool_list
