# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 用户目标拆解与规划"""
from typing import Any
from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.llm.reasoning import ReasoningLLM
from apps.llm.function import JsonGenerator
from apps.scheduler.mcp_agent.prompt import EVALUATE_GAOL, CREATE_PLAN, RECREATE_PLAN, FINAL_ANSWER
from apps.schemas.mcp import (
    GoalEvaluationResult,
    MCPPlan,
    MCPTool
)


class MCPPlanner:
    """MCP 用户目标拆解与规划"""

    def __init__(self, user_goal: str, resoning_llm: ReasoningLLM = None) -> None:
        """初始化MCP规划器"""
        self.user_goal = user_goal
        self._env = SandboxedEnvironment(
            loader=BaseLoader,
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.input_tokens = 0
        self.output_tokens = 0
        self.resoning_llm = resoning_llm or ReasoningLLM()

    async def get_resoning_result(self, prompt: str) -> str:
        """获取推理结果"""
        # 调用推理大模型
        message = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
        result = ""
        async for chunk in self.resoning_llm.call(
            message,
            streaming=False,
            temperature=0.07,
            result_only=True,
        ):
            result += chunk

        # 保存token用量
        self.input_tokens = self.resoning_llm.input_tokens
        self.output_tokens = self.resoning_llm.output_tokens
        return result

    async def _parse_result(self, result: str, schema: dict[str, Any]) -> str:
        """解析推理结果"""
        json_generator = JsonGenerator(
            result,
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": result},
            ],
            schema,
        )
        json_result = await json_generator.generate()
        return json_result

    async def evaluate_goal(self, tool_list: list[MCPTool]) -> str:
        pass

    async def _get_reasoning_evaluation(self, tool_list: list[MCPTool]) -> str:
        """获取推理大模型的评估结果"""
        template = self._env.from_string(EVALUATE_GAOL)
        prompt = template.render(
            goal=self.user_goal,
            tools=tool_list,
        )
        result = await self.get_resoning_result(prompt)
        return result

    async def _parse_evaluation_result(self, result: str) -> str:
        """将推理结果解析为结构化数据"""
        schema = GoalEvaluationResult.model_json_schema()
        evaluation = await self._parse_result(result, schema)
        # 使用GoalEvaluationResult模型解析结果
        return GoalEvaluationResult.model_validate(evaluation)

    async def create_plan(self, tool_list: list[MCPTool], max_steps: int = 6) -> MCPPlan:
        """规划下一步的执行流程，并输出"""
        # 获取推理结果
        result = await self._get_reasoning_plan(tool_list, max_steps)

        # 解析为结构化数据
        return await self._parse_plan_result(result, max_steps)

    async def _get_reasoning_plan(
            self, is_replan: bool = False, error_message: str = "", current_plan: MCPPlan = MCPPlan(),
            tool_list: list[MCPTool] = [],
            max_steps: int = 10) -> str:
        """获取推理大模型的结果"""
        # 格式化Prompt
        if is_replan:
            template = self._env.from_string(RECREATE_PLAN)
            prompt = template.render(
                current_plan=current_plan,
                error_message=error_message,
                goal=self.user_goal,
                tools=tool_list,
                max_num=max_steps,
            )
        else:
            template = self._env.from_string(CREATE_PLAN)
            prompt = template.render(
                goal=self.user_goal,
                tools=tool_list,
                max_num=max_steps,
            )
        result = await self.get_resoning_result(prompt)
        return result

    async def _parse_plan_result(self, result: str, max_steps: int) -> MCPPlan:
        """将推理结果解析为结构化数据"""
        # 格式化Prompt
        schema = MCPPlan.model_json_schema()
        schema["properties"]["plans"]["maxItems"] = max_steps
        plan = await self._parse_result(result, schema)
        # 使用Function模型解析结果
        return MCPPlan.model_validate(plan)

    async def generate_answer(self, plan: MCPPlan, memory: str) -> str:
        """生成最终回答"""
        template = self._env.from_string(FINAL_ANSWER)
        prompt = template.render(
            plan=plan,
            memory=memory,
            goal=self.user_goal,
        )

        llm = ReasoningLLM()
        result = ""
        async for chunk in llm.call(
            [{"role": "user", "content": prompt}],
            streaming=False,
            temperature=0.07,
        ):
            result += chunk

        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        return result
