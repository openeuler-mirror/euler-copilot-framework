# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 用户目标拆解与规划"""

import copy
import logging

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.llm import LLM, json_generator
from apps.models import LanguageType, MCPTools
from apps.schemas.mcp import MCPPlan

from .base import MCPNodeBase
from .prompt import CREATE_MCP_PLAN_FUNCTION, FINAL_ANSWER

_logger = logging.getLogger(__name__)

class MCPPlanner(MCPNodeBase):
    """MCP 用户目标拆解与规划"""

    def __init__(self, user_goal: str, language: LanguageType, llm: LLM) -> None:
        """初始化MCP规划器"""
        super().__init__(llm, language)
        self._user_goal = user_goal
        self._env = SandboxedEnvironment(
            loader=BaseLoader,
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )


    async def create_plan(self, tool_list: list[MCPTools], max_steps: int = 6) -> MCPPlan:
        """规划下一步的执行流程，并输出"""
        # 格式化Prompt
        template = self._env.from_string(await self._load_prompt("create_plan"))
        prompt = template.render(
            goal=self._user_goal,
            tools=tool_list,
            max_num=max_steps,
        )

        function_def = CREATE_MCP_PLAN_FUNCTION[self._language].copy()
        function_def["parameters"] = copy.deepcopy(function_def["parameters"])
        function_def["parameters"]["properties"]["plans"]["maxItems"] = max_steps

        # 使用json_generator直接生成结构化plan
        plan = await json_generator.generate(
            function=function_def,
            conversation=[
                {"role": "system", "content": "You are a helpful assistant."},
            ],
            prompt=prompt,
        )
        return MCPPlan.model_validate(plan)


    async def generate_answer(self, plan: MCPPlan, memory: str) -> str:
        """生成最终回答"""
        template = self._env.from_string(FINAL_ANSWER[self._language])
        prompt = template.render(
            plan=plan,
            memory=memory,
            goal=self._user_goal,
        )

        result = ""
        async for chunk in self._llm.call(
            [{"role": "user", "content": prompt}],
            streaming=False,
        ):
            result += chunk.content or ""

        return result
