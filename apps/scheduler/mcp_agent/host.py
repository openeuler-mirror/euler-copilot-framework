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
from apps.schemas.enum_var import StepStatus
from apps.schemas.mcp import MCPPlanItem, MCPTool
from apps.schemas.task import FlowStepHistory
from apps.services.task import TaskManager

logger = logging.getLogger(__name__)


class MCPHost:
    """MCP宿主服务"""

    def __init__(self, user_sub: str, task_id: str, runtime_id: str, runtime_name: str) -> None:
        """初始化MCP宿主"""
        self._user_sub = user_sub
        self._task_id = task_id
        # 注意：runtime在工作流中是flow_id和step_description，在Agent中可为标识Agent的id和description
        self._runtime_id = runtime_id
        self._runtime_name = runtime_name
        self._context_list = []
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    async def get_client(self, mcp_id: str) -> MCPClient | None:
        """获取MCP客户端"""
        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")

        # 检查用户是否启用了这个mcp
        mcp_db_result = await mcp_collection.find_one({"_id": mcp_id, "activated": self._user_sub})
        if not mcp_db_result:
            logger.warning("用户 %s 未启用MCP %s", self._user_sub, mcp_id)
            return None

        # 获取MCP配置
        try:
            return await MCPPool().get(mcp_id, self._user_sub)
        except KeyError:
            logger.warning("用户 %s 的MCP %s 没有运行中的实例，请检查环境", self._user_sub, mcp_id)
            return None

    async def assemble_memory(self) -> str:
        """组装记忆"""
        task = await TaskManager.get_task_by_task_id(self._task_id)
        if not task:
            logger.error("任务 %s 不存在", self._task_id)
            return ""

        context_list = []
        for ctx_id in self._context_list:
            context = next((ctx for ctx in task.context if ctx["_id"] == ctx_id), None)
            if not context:
                continue
            context_list.append(context)

        return self._env.from_string(MEMORY_TEMPLATE).render(
            context_list=context_list,
        )

    async def _save_memory(
        self,
        tool: MCPTool,
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

        # 创建context；注意用法
        context = FlowStepHistory(
            task_id=self._task_id,
            flow_id=self._runtime_id,
            flow_name=self._runtime_name,
            flow_status=StepStatus.SUCCESS,
            step_id=tool.name,
            step_name=tool.name,
            # description是规划的实际内容
            step_description=plan_item.content,
            step_status=StepStatus.SUCCESS,
            input_data=input_data,
            output_data=output_data,
        )

        # 保存到task
        task = await TaskManager.get_task_by_task_id(self._task_id)
        if not task:
            logger.error("任务 %s 不存在", self._task_id)
            return {}
        self._context_list.append(context.id)
        task.context.append(context.model_dump(by_alias=True, exclude_none=True))
        await TaskManager.save_task(self._task_id, task)

        return output_data

    async def _fill_params(self, tool: MCPTool, query: str) -> dict[str, Any]:
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
                {"role": "user", "content": await self.assemble_memory()},
            ],
            tool.input_schema,
        )
        return await json_generator.generate()

    async def call_tool(self, tool: MCPTool, plan_item: MCPPlanItem) -> list[dict[str, Any]]:
        """调用工具"""
        # 拿到Client
        client = await MCPPool().get(tool.mcp_id, self._user_sub)
        if client is None:
            err = f"[MCPHost] MCP Server不合法: {tool.mcp_id}"
            logger.error(err)
            raise ValueError(err)

        # 填充参数
        params = await self._fill_params(tool, plan_item.instruction)
        # 调用工具
        result = await client.call_tool(tool.name, params)
        # 保存记忆
        processed_result = []
        for item in result.content:
            if not isinstance(item, TextContent):
                logger.error("MCP结果类型不支持: %s", item)
                continue
            processed_result.append(await self._save_memory(tool, plan_item, params, item.text))

        return processed_result

    async def get_tool_list(self, mcp_id_list: list[str]) -> list[MCPTool]:
        """获取工具列表"""
        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")

        # 获取工具列表
        tool_list = []
        for mcp_id in mcp_id_list:
            # 检查用户是否启用了这个mcp
            mcp_db_result = await mcp_collection.find_one({"_id": mcp_id, "activated": self._user_sub})
            if not mcp_db_result:
                logger.warning("用户 %s 未启用MCP %s", self._user_sub, mcp_id)
                continue
            # 获取MCP工具配置
            try:
                for tool in mcp_db_result["tools"]:
                    tool_list.extend([MCPTool.model_validate(tool)])
            except KeyError:
                logger.warning("用户 %s 的MCP Tool %s 配置错误", self._user_sub, mcp_id)
                continue

        return tool_list
