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
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


class MCPHost:
    """MCP宿主服务"""

    @staticmethod
    async def get_client(user_sub, mcp_id: str) -> MCPClient | None:
        """获取MCP客户端"""
        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")

        # 检查用户是否启用了这个mcp
        mcp_db_result = await mcp_collection.find_one({"_id": mcp_id, "activated": user_sub})
        if not mcp_db_result:
            logger.warning("用户 %s 未启用MCP %s", user_sub, mcp_id)
            return None

        # 获取MCP配置
        try:
            return await MCPPool().get(mcp_id, user_sub)
        except KeyError:
            logger.warning("用户 %s 的MCP %s 没有运行中的实例，请检查环境", user_sub, mcp_id)
            return None

    @staticmethod
    async def assemble_memory(task: Task) -> str:
        """组装记忆"""

        return _env.from_string(MEMORY_TEMPLATE).render(
            context_list=task.context,
        )

    async def _get_first_input_params(schema: dict[str, Any], query: str) -> dict[str, Any]:
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
                {"role": "user", "content": await MCPHost.assemble_memory()},
            ],
            schema,
        )
        return await json_generator.generate()

    async def _fill_params(mcp_tool: MCPTool, schema: dict[str, Any],
                           current_input: dict[str, Any],
                           error_message: str = "", params: dict[str, Any] = {},
                           params_description: str = "") -> dict[str, Any]:
        llm_query = "请生成修复之后的工具参数"
        prompt = _env.from_string(REPAIR_PARAMS).render(
            tool_name=mcp_tool.name,
            tool_description=mcp_tool.description,
            input_schema=schema,
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
            schema,
        )
        return await json_generator.generate()

    async def call_tool(user_sub: str, tool: MCPTool, plan_item: MCPPlanItem) -> list[dict[str, Any]]:
        """调用工具"""
        # 拿到Client
        client = await MCPPool().get(tool.mcp_id, user_sub)
        if client is None:
            err = f"[MCPHost] MCP Server不合法: {tool.mcp_id}"
            logger.error(err)
            raise ValueError(err)

        # 填充参数
        params = await MCPHost._fill_params(tool, plan_item.instruction)
        # 调用工具
        result = await client.call_tool(tool.name, params)
        # 保存记忆
        processed_result = []
        for item in result.content:
            if not isinstance(item, TextContent):
                logger.error("MCP结果类型不支持: %s", item)
                continue
            result = item.text
            try:
                json_result = json.loads(result)
            except Exception as e:
                logger.error("MCP结果解析失败: %s, 错误: %s", result, e)
                continue
            processed_result.append(json_result)

        return processed_result
