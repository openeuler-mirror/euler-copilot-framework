# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""选择MCP Server及其工具"""

import logging

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.common.lance import LanceDB
from apps.common.mongo import MongoDB
from apps.llm.embedding import Embedding
from apps.llm.function import FunctionLLM
from apps.llm.reasoning import ReasoningLLM
from apps.scheduler.mcp.prompt import (
    MCP_SELECT,
)
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
    def _assemble_sql(mcp_list: list[str]) -> str:
        """组装SQL"""
        sql = "("
        for mcp_id in mcp_list:
            sql += f"'{mcp_id}', "
        return sql.rstrip(", ") + ")"


    async def _get_top_mcp_by_embedding(
        self,
        query: str,
        mcp_list: list[str],
    ) -> list[dict[str, str]]:
        """通过向量检索获取Top5 MCP Server"""
        logger.info("[MCPHelper] 查询MCP Server向量: %s, %s", query, mcp_list)
        mcp_table = await LanceDB().get_table("mcp")
        query_embedding = await Embedding.get_embedding([query])
        mcp_vecs = await (await mcp_table.search(
            query=query_embedding,
            vector_column_name="embedding",
        )).where(f"id IN {MCPSelector._assemble_sql(mcp_list)}").limit(5).to_list()

        # 拿到名称和description
        logger.info("[MCPHelper] 查询MCP Server名称和描述: %s", mcp_vecs)
        mcp_collection = MongoDB().get_collection("mcp")
        llm_mcp_list: list[dict[str, str]] = []
        for mcp_vec in mcp_vecs:
            mcp_id = mcp_vec["id"]
            mcp_data = await mcp_collection.find_one({"_id": mcp_id})
            if not mcp_data:
                logger.warning("[MCPHelper] 查询MCP Server名称和描述失败: %s", mcp_id)
                continue
            mcp_data = MCPCollection.model_validate(mcp_data)
            llm_mcp_list.extend([{
                "id": mcp_id,
                "name": mcp_data.name,
                "description": mcp_data.description,
            }])
        return llm_mcp_list


    async def _get_mcp_by_llm(
        self,
        query: str,
        mcp_list: list[dict[str, str]],
        mcp_ids: list[str],
    ) -> MCPSelectResult:
        """通过LLM选择最合适的MCP Server"""
        # 初始化jinja2环境
        env = SandboxedEnvironment(
            loader=BaseLoader,
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template = env.from_string(MCP_SELECT)
        # 渲染模板
        mcp_prompt = template.render(
            mcp_list=mcp_list,
            goal=query,
        )

        # 调用大模型进行推理
        result = await self._call_reasoning(mcp_prompt)

        # 使用小模型提取JSON
        return await self._call_function_mcp(result, mcp_ids)


    async def _call_reasoning(self, prompt: str) -> str:
        """调用大模型进行推理"""
        logger.info("[MCPHelper] 调用推理大模型")
        llm = ReasoningLLM()
        message = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
        result = ""
        async for chunk in llm.call(message):
            result += chunk
        self.input_tokens += llm.input_tokens
        self.output_tokens += llm.output_tokens
        return result


    async def _call_function_mcp(self, reasoning_result: str, mcp_ids: list[str]) -> MCPSelectResult:
        """调用结构化输出小模型提取JSON"""
        logger.info("[MCPHelper] 调用结构化输出小模型")
        llm = FunctionLLM()
        message = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": reasoning_result},
        ]
        schema = MCPSelectResult.model_json_schema()
        # schema中加入选项
        schema["properties"]["mcp_id"]["enum"] = mcp_ids
        result = await llm.call(messages=message, schema=schema)
        try:
            result = MCPSelectResult.model_validate(result)
        except Exception:
            logger.exception("[MCPHelper] 解析MCP Select Result失败")
            raise
        return result


    async def select_top_mcp(
        self,
        query: str,
        mcp_list: list[str],
    ) -> MCPSelectResult:
        """
        选择最合适的MCP Server

        先通过Embedding选择Top5，然后通过LLM选择Top 1
        """
        # 通过向量检索获取Top5
        llm_mcp_list = await self._get_top_mcp_by_embedding(query, mcp_list)

        # 通过LLM选择最合适的
        return await self._get_mcp_by_llm(query, llm_mcp_list, mcp_list)


    @staticmethod
    async def select_top_tool(query: str, mcp_list: list[str], top_n: int = 10) -> list[MCPTool]:
        """选择最合适的工具"""
        tool_vector = await LanceDB().get_table("mcp_tool")
        query_embedding = await Embedding.get_embedding([query])
        tool_vecs = await (await tool_vector.search(
            query=query_embedding,
            vector_column_name="embedding",
        )).where(f"mcp_id IN {MCPSelector._assemble_sql(mcp_list)}").limit(top_n).to_list()

        # 拿到工具
        tool_collection = MongoDB().get_collection("mcp")
        llm_tool_list = []

        for tool_vec in tool_vecs:
            # 到MongoDB里找对应的工具
            logger.info("[MCPHelper] 查询MCP Tool名称和描述: %s", tool_vec["mcp_id"])
            tool_data = await tool_collection.aggregate([
                {"$match": {"_id": tool_vec["mcp_id"]}},
                {"$unwind": "$tools"},
                {"$match": {"tools.id": tool_vec["id"]}},
                {"$project": {"_id": 0, "tools": 1}},
                {"$replaceRoot": {"newRoot": "$tools"}},
            ])
            async for tool in tool_data:
                tool_obj = MCPTool.model_validate(tool)
                llm_tool_list.append(tool_obj)

        return llm_tool_list
