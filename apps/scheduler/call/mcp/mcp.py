# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP工具"""

import logging
from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import Any

from pydantic import Field

from apps.scheduler.call.core import CallError, CoreCall
from apps.scheduler.call.mcp.schema import (
    MCPInput,
    MCPMessage,
    MCPMessageType,
    MCPOutput,
)
from apps.scheduler.mcp import MCPHost, MCPPlanner, MCPSelector
from apps.schemas.enum_var import CallOutputType
from apps.schemas.mcp import MCPPlanItem
from apps.schemas.scheduler import (
    CallInfo,
    CallOutputChunk,
    CallVars,
)

logger = logging.getLogger(__name__)


class MCP(CoreCall, input_model=MCPInput, output_model=MCPOutput):
    """MCP工具"""

    mcp_list: list[str] = Field(description="MCP Server ID列表", max_length=5, min_length=1)
    max_steps: int = Field(description="最大步骤数", default=6)
    text_output: bool = Field(description="是否将结果以文本形式返回", default=True)
    to_user: bool = Field(description="是否将结果返回给用户", default=True)

    @classmethod
    def info(cls) -> CallInfo:
        """
        返回Call的名称和描述

        :return: Call的名称和描述
        :rtype: CallInfo
        """
        return CallInfo(name="MCP", description="调用MCP Server，执行工具")

    async def _init(self, call_vars: CallVars) -> MCPInput:
        """初始化MCP"""
        # 获取MCP交互类
        self._host = MCPHost(call_vars.ids.user_sub, call_vars.ids.task_id, call_vars.ids.flow_id, self.description)
        self._tool_list = await self._host.get_tool_list(self.mcp_list)
        self._call_vars = call_vars

        # 获取工具列表
        avaliable_tools = {}
        for tool in self._tool_list:
            if tool.mcp_id not in avaliable_tools:
                avaliable_tools[tool.mcp_id] = []
            avaliable_tools[tool.mcp_id].append(tool.name)

        return MCPInput(avaliable_tools=avaliable_tools, max_steps=self.max_steps)

    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行MCP"""
        # 生成计划
        async for chunk in self._generate_plan():
            yield chunk

        # 执行计划
        plan_list = deepcopy(self._plan.plans)
        while len(plan_list) > 0:
            async for chunk in self._execute_plan_item(plan_list.pop(0)):
                yield chunk

        # 生成总结
        async for chunk in self._generate_answer():
            yield chunk

    async def _generate_plan(self) -> AsyncGenerator[CallOutputChunk, None]:
        """生成执行计划"""
        # 开始提示
        yield self._create_output("[MCP] 开始生成计划...\n\n\n\n", MCPMessageType.PLAN_BEGIN)

        # 选择工具并生成计划
        selector = MCPSelector()
        top_tool = await selector.select_top_tool(self._call_vars.question, self.mcp_list)
        planner = MCPPlanner(self._call_vars.question)
        self._plan = await planner.create_plan(top_tool, self.max_steps)

        # 输出计划
        plan_str = "\n\n"
        for plan_item in self._plan.plans:
            plan_str += f"[+] {plan_item.content}； {plan_item.tool}[{plan_item.instruction}]\n\n"

        yield self._create_output(
            f"[MCP] 计划生成完成：\n\n{plan_str}\n\n\n\n",
            MCPMessageType.PLAN_END,
            data=self._plan.model_dump(),
        )

    async def _execute_plan_item(self, plan_item: MCPPlanItem) -> AsyncGenerator[CallOutputChunk, None]:
        """执行单个计划项"""
        # 判断是否为Final
        if plan_item.tool == "Final":
            return

        # 获取工具
        tool = next((tool for tool in self._tool_list if tool.id == plan_item.tool), None)
        if tool is None:
            err = f"[MCP] 工具 {plan_item.tool} 不存在"
            logger.error(err)
            raise CallError(err, data={})

        # 提示开始调用
        yield self._create_output(
            f"[MCP] 正在调用工具 {tool.name}...\n\n",
            MCPMessageType.TOOL_BEGIN,
        )

        # 调用工具
        try:
            result = await self._host.call_tool(tool, plan_item)
        except Exception as e:
            err = f"[MCP] 工具 {tool.name} 调用失败: {e!s}"
            logger.exception(err)
            raise CallError(err, data={}) from e

        # 提示调用完成
        logger.info("[MCP] 工具 %s 调用完成, 结果: %s", tool.name, result)
        yield self._create_output(
            f"[MCP] 工具 {tool.name} 调用完成\n\n",
            MCPMessageType.TOOL_END,
            data={
                "data": result,
            },
        )

    async def _generate_answer(self) -> AsyncGenerator[CallOutputChunk, None]:
        """生成总结"""
        # 提示开始总结
        yield self._create_output(
            "[MCP] 正在总结任务结果...\n\n",
            MCPMessageType.FINISH_BEGIN,
        )

        # 生成答案
        planner = MCPPlanner(self._call_vars.question)
        answer = await planner.generate_answer(self._plan, await self._host.assemble_memory())

        # 输出结果
        yield self._create_output(
            f"[MCP] 任务完成\n\n---\n\n{answer}\n\n",
            MCPMessageType.FINISH_END,
            data=MCPOutput(
                message=answer,
            ).model_dump(),
        )

    def _create_output(
        self,
        text: str,
        msg_type: MCPMessageType,
        data: dict[str, Any] | None = None,
    ) -> CallOutputChunk:
        """创建输出"""
        if self.text_output:
            return CallOutputChunk(type=CallOutputType.TEXT, content=text)
        return CallOutputChunk(type=CallOutputType.DATA, content=MCPMessage(
            msg_type=msg_type,
            message=text.strip(),
            data=data or {},
        ).model_dump_json())
