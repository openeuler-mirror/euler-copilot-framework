# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP宿主"""

import json
import logging
import uuid
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from mcp.types import TextContent

from apps.llm import LLM, json_generator
from apps.models import LanguageType, MCPTools
from apps.scheduler.mcp.prompt import FILL_PARAMS_QUERY, MEMORY_TEMPLATE
from apps.scheduler.pool.mcp.client import MCPClient
from apps.scheduler.pool.mcp.pool import mcp_pool
from apps.schemas.mcp import MCPContext, MCPPlanItem
from apps.services.mcp_service import MCPServiceManager

logger = logging.getLogger(__name__)


class MCPHost:
    """MCP宿主服务"""

    def __init__(self, user_id: str, task_id: uuid.UUID, llm: LLM, language: LanguageType) -> None:
        """初始化MCP宿主"""
        self._task_id = task_id
        self._user_id = user_id
        self._context_list = []
        self._language = language
        self._llm = llm
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    async def init(self) -> None:
        """初始化MCP宿主"""


    async def get_client(self, mcp_id: str) -> MCPClient | None:
        """获取MCP客户端"""
        if not await MCPServiceManager.is_user_actived(self._user_id, mcp_id):
            logger.warning("用户 %s 未启用MCP %s", self._user_id, mcp_id)
            return None

        # 获取MCP配置
        try:
            return await mcp_pool.get(mcp_id, self._user_id)
        except KeyError:
            logger.warning("用户 %s 的MCP %s 没有运行中的实例，请检查环境", self._user_id, mcp_id)
            return None


    async def assemble_memory(self) -> list[dict[str, str]]:
        """组装记忆，返回虚拟的用户与助手间的对话历史"""
        # 从host的context_list中获取context
        context_list = self._context_list

        # 构建对话历史列表
        conversation_history = []
        template = self._env.from_string(MEMORY_TEMPLATE[self._language])

        for index, ctx in enumerate(context_list, start=1):
            # 生成user消息（工具调用）
            user_message = template.render(
                msg_type="user",
                step_index=index,
                step_description=ctx.step_description,
                step_name=ctx.step_name,
                input_data=ctx.input_data,
            )
            conversation_history.append({
                "role": "user",
                "content": user_message.strip(),
            })

            # 生成assistant消息（工具输出）
            assistant_message = template.render(
                msg_type="assistant",
                step_index=index,
                step_status=ctx.step_status,
                output_data=ctx.output_data,
            )
            conversation_history.append({
                "role": "assistant",
                "content": assistant_message.strip(),
            })

        return conversation_history


    async def _save_memory(
        self,
        tool: MCPTools,
        plan_item: MCPPlanItem,
        input_data: dict[str, Any],
        result: str,
    ) -> dict[str, Any]:
        """保存记忆"""
        try:
            output_data = json.loads(result)
        except Exception:  # noqa: BLE001
            logger.warning("[MCPHost] 得到的数据不是dict格式！尝试转换为str")
            output_data = {
                "message": result,
            }

        if not isinstance(output_data, dict):
            output_data = {
                "message": result,
            }

        # 创建简化版context
        context = MCPContext(
            step_description=plan_item.content,
            input_data=input_data,
            output_data=output_data,
        )

        # 保存到host的context_list
        self._context_list.append(context)

        return output_data


    async def _fill_params(self, tool: MCPTools, query: str) -> dict[str, Any]:
        """填充工具参数"""
        # 使用Jinja2模板生成查询
        template = self._env.from_string(FILL_PARAMS_QUERY[self._language])
        llm_query = template.render(
            instruction=query,
            tool_name=tool.toolName,
            tool_description=tool.description,
        )

        function_definition = {
            "name": tool.toolName,
            "description": tool.description,
            "parameters": tool.inputSchema,
        }

        # 获取历史对话记录并添加当前查询
        memory_conversation = await self.assemble_memory()
        conversation = [
            *memory_conversation,
            {"role": "user", "content": llm_query},
        ]

        # 使用全局json_generator实例
        return await json_generator.generate(
            function=function_definition,
            conversation=conversation,
            language=self._language,
        )


    async def call_tool(self, tool: MCPTools, plan_item: MCPPlanItem) -> list[dict[str, Any]]:
        """调用工具"""
        # 拿到Client
        client = await mcp_pool.get(tool.mcpId, self._user_id)
        if client is None:
            err = f"[MCPHost] MCP Server不合法: {tool.mcpId}"
            logger.error(err)
            raise ValueError(err)

        # 填充参数
        params = await self._fill_params(tool, plan_item.instruction)
        # 调用工具
        result = await client.call_tool(tool.toolName, params)
        # 保存记忆
        processed_result = []
        for item in result.content:
            if not isinstance(item, TextContent):
                logger.error("MCP结果类型不支持: %s", item)
                continue
            processed_result.append(await self._save_memory(tool, plan_item, params, item.text))

        return processed_result


    async def get_tool_list(self, mcp_id_list: list[str]) -> list[MCPTools]:
        """获取工具列表"""
        # 获取工具列表
        tool_list = []
        for mcp_id in mcp_id_list:
            # 检查用户是否启用了这个mcp
            if not await MCPServiceManager.is_user_actived(self._user_id, mcp_id):
                logger.warning("用户 %s 未启用MCP %s", self._user_id, mcp_id)
                continue
            # 获取MCP工具配置
            try:
                tool_list.extend(await MCPServiceManager.get_mcp_tools(mcp_id))
            except KeyError:
                logger.warning("用户 %s 的MCP Tool %s 配置错误", self._user_id, mcp_id)
                continue

        return tool_list
