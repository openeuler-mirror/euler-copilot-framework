# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP工具"""

import logging
from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import Any, ClassVar

from pydantic import Field
from apps.scheduler.call.core import CallError, CoreCall
from apps.scheduler.call.mcp.schema import (
    MCPInput,
    MCPMessage,
    MCPMessageType,
    MCPOutput,
)
from apps.scheduler.mcp import MCPHost, MCPPlanner, MCPSelector
from apps.schemas.enum_var import CallOutputType, CallType, LanguageType
from apps.schemas.mcp import MCPPlanItem
from apps.schemas.scheduler import (
    CallInfo,
    CallOutputChunk,
    CallVars,
)

logger = logging.getLogger(__name__)

MCP_GENERATE: dict[str, dict[LanguageType, str]] = {
    "START": {
        LanguageType.CHINESE: "[MCP] 开始生成计划...\n\n\n\n",
        LanguageType.ENGLISH: "[MCP] Start generating plan...\n\n\n\n",
    },
    "END": {
        LanguageType.CHINESE: "[MCP] 计划生成完成：\n\n{plan_str}\n\n\n\n",
        LanguageType.ENGLISH: "[MCP] Plan generation completed: \n\n{plan_str}\n\n\n\n",
    },
}

MCP_SUMMARY: dict[str, dict[LanguageType, str]] = {
    "START": {
        LanguageType.CHINESE: "[MCP] 正在总结任务结果...\n\n",
        LanguageType.ENGLISH: "[MCP] Start summarizing task results...\n\n",
    },
    "END": {
        LanguageType.CHINESE: "[MCP] 任务完成\n\n---\n\n{answer}\n\n",
        LanguageType.ENGLISH: "[MCP] Task summary completed\n\n{answer}\n\n",
    },
}


class MCP(CoreCall, input_model=MCPInput, output_model=MCPOutput):
    """MCP工具"""

    controlled_output: bool = Field(default=True)

    # 输出参数配置
    output_parameters: dict[str, Any] = Field(description="输出参数配置", default={
        "message": {"type": "string", "description": "MCP Server的自然语言输出"},
    })

    mcp_list: list[str] = Field(
        description="MCP Server ID列表", max_length=15, min_length=1)
    max_steps: int = Field(description="最大步骤数", default=20)
    text_output: bool = Field(description="是否将结果以文本形式返回", default=True)
    to_user: bool = Field(description="是否将结果返回给用户", default=True)

    i18n_info: ClassVar[dict[str, dict]] = {
        LanguageType.CHINESE: {
            "name": "MCP",
            "type": CallType.DEFAULT,
            "description": "调用MCP Server，执行工具",
        },
        LanguageType.ENGLISH: {
            "name": "MCP",
            "type": CallType.DEFAULT,
            "description": "Call the MCP Server to execute tools",
        },
    }

    async def _init(self, call_vars: CallVars) -> MCPInput:
        """初始化MCP"""
        # 获取MCP交互类
        from apps.services.appcenter import AppCenterManager
        app = await AppCenterManager.fetch_app_data_by_id(call_vars.ids.app_id)
        self._host = MCPHost(app.author, self.mcp_list, call_vars.ids.task_id,
                             call_vars.ids.flow_id, self.description)
        self._tool_list = await self._host.get_tool_list(self.mcp_list)
        self._call_vars = call_vars

        # 获取工具列表
        avaliable_tools = {}
        for tool in self._tool_list:
            if tool.mcp_id not in avaliable_tools:
                avaliable_tools[tool.mcp_id] = []
            avaliable_tools[tool.mcp_id].append(tool.name)

        return MCPInput(avaliable_tools=avaliable_tools, max_steps=self.max_steps)

    async def _exec(
        self, input_data: dict[str, Any], language: LanguageType = LanguageType.CHINESE
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """执行MCP"""
        # 生成计划
        async for chunk in self._generate_plan(language):
            yield chunk

        # 执行计划
        plan_list = deepcopy(self._plan.plans)
        while len(plan_list) > 0:
            async for chunk in self._execute_plan_item(plan_list.pop(0), language):
                yield chunk

        # 生成总结
        async for chunk in self._generate_answer(language):
            yield chunk

    async def _generate_plan(self, language: LanguageType = LanguageType.CHINESE) -> AsyncGenerator[CallOutputChunk, None]:
        """生成执行计划"""
        # 开始提示
        yield self._create_output(MCP_GENERATE["START"][language], MCPMessageType.PLAN_BEGIN)

        # 选择工具并生成计划
        selector = MCPSelector()
        top_tool = await selector.select_top_tool(self._call_vars.question, self.mcp_list)
        planner = MCPPlanner(self._call_vars.question, language)
        self._plan = await planner.create_plan(top_tool, self.max_steps)

        # 输出计划
        plan_str = "\n\n"
        for plan_item in self._plan.plans:
            plan_str += f"[+] {plan_item.content}； {plan_item.tool}[{plan_item.instruction}]\n\n"

        yield self._create_output(
            MCP_GENERATE["END"][language].format(plan_str=plan_str),
            MCPMessageType.PLAN_END,
            data=self._plan.model_dump(),
        )

    async def _execute_plan_item(
        self, plan_item: MCPPlanItem, language: LanguageType = LanguageType.CHINESE
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """执行单个计划项"""
        # 判断是否为Final
        if plan_item.tool == "Final":
            return
        self._host.language = language
        # 获取工具
        tool = next(
            (tool for tool in self._tool_list if tool.id == plan_item.tool), None)
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

    async def _generate_answer(self, language: LanguageType = LanguageType.CHINESE) -> AsyncGenerator[CallOutputChunk, None]:
        """生成总结"""
        # 提示开始总结
        yield self._create_output(
            MCP_SUMMARY["START"][language],
            MCPMessageType.FINISH_BEGIN,
        )

        # 生成答案
        planner = MCPPlanner(self._call_vars.question, language)
        answer = await planner.generate_answer(self._plan, await self._host.assemble_memory())

        # 输出文本结果
        yield self._create_output(
            MCP_SUMMARY["END"][language].format(answer=answer),
            MCPMessageType.FINISH_END,
            data=MCPOutput(
                message=answer,
            ).model_dump(),
        )

        # 额外输出一个纯DATA chunk用于保存到变量池
        yield CallOutputChunk(
            type=CallOutputType.DATA,
            content=MCPOutput(message=answer).model_dump(
                by_alias=True, exclude_none=True)
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
        return CallOutputChunk(
            type=CallOutputType.DATA,
            content=MCPMessage(
                msg_type=msg_type,
                message=text.strip(),
                data=data or {},
            ).model_dump_json(),
        )
