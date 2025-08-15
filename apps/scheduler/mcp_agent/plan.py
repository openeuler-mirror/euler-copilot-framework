# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 用户目标拆解与规划"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.llm.reasoning import ReasoningLLM
from apps.scheduler.mcp_agent.base import MCPBase
from apps.scheduler.mcp_agent.prompt import (
    CHANGE_ERROR_MESSAGE_TO_DESCRIPTION,
    CREATE_PLAN,
    EVALUATE_GOAL,
    FINAL_ANSWER,
    GEN_STEP,
    GENERATE_FLOW_NAME,
    GET_MISSING_PARAMS,
    GET_REPLAN_START_STEP_INDEX,
    IS_PARAM_ERROR,
    RECREATE_PLAN,
    RISK_EVALUATE,
    TOOL_EXECUTE_ERROR_TYPE_ANALYSIS,
    TOOL_SKIP,
)
from apps.schemas.enum_var import LanguageType
from apps.scheduler.slot.slot import Slot
from apps.schemas.mcp import (
    GoalEvaluationResult,
    IsParamError,
    MCPPlan,
    MCPTool,
    RestartStepIndex,
    Step,
    ToolExcutionErrorType,
    ToolRisk,
    ToolSkip,
)
from apps.schemas.task import Task

_env = SandboxedEnvironment(
    loader=BaseLoader,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)
logger = logging.getLogger(__name__)


class MCPPlanner(MCPBase):
    """MCP 用户目标拆解与规划"""

    @staticmethod
    async def evaluate_goal(
        goal: str, tool_list: list[MCPTool], resoning_llm: ReasoningLLM = ReasoningLLM(), language: LanguageType = LanguageType.CHINESE,
    ) -> GoalEvaluationResult:
        """评估用户目标的可行性"""
        # 获取推理结果
        result = await MCPPlanner._get_reasoning_evaluation(goal, tool_list, resoning_llm, language)

        # 返回评估结果
        return await MCPPlanner._parse_evaluation_result(result)

    @staticmethod
    async def _get_reasoning_evaluation(
        goal, tool_list: list[MCPTool], resoning_llm: ReasoningLLM = ReasoningLLM(), language: LanguageType = LanguageType.CHINESE,
    ) -> str:
        """获取推理大模型的评估结果"""
        template = _env.from_string(EVALUATE_GOAL[language])
        prompt = template.render(
            goal=goal,
            tools=tool_list,
        )
        return await MCPPlanner.get_resoning_result(prompt, resoning_llm)

    @staticmethod
    async def _parse_evaluation_result(result: str) -> GoalEvaluationResult:
        """将推理结果解析为结构化数据"""
        schema = GoalEvaluationResult.model_json_schema()
        evaluation = await MCPPlanner._parse_result(result, schema)
        # 使用GoalEvaluationResult模型解析结果
        return GoalEvaluationResult.model_validate(evaluation)

    async def get_flow_name(
        user_goal: str,
        resoning_llm: ReasoningLLM = ReasoningLLM(),
        language: LanguageType = LanguageType.CHINESE,
    ) -> str:
        """获取当前流程的名称"""

        return await MCPPlanner._get_reasoning_flow_name(user_goal, resoning_llm, language)

    @staticmethod
    async def _get_reasoning_flow_name(
        user_goal: str,
        resoning_llm: ReasoningLLM = ReasoningLLM(),
        language: LanguageType = LanguageType.CHINESE,
    ) -> str:
        """获取推理大模型的流程名称"""
        template = _env.from_string(GENERATE_FLOW_NAME[language])
        prompt = template.render(goal=user_goal)
        return await MCPPlanner.get_resoning_result(prompt, resoning_llm)

    @staticmethod
    async def get_replan_start_step_index(
        user_goal: str,
        error_message: str,
        current_plan: MCPPlan | None = None,
        history: str = "",
        reasoning_llm: ReasoningLLM = ReasoningLLM(),
        language: LanguageType = LanguageType.CHINESE,
    ) -> RestartStepIndex:
        """获取重新规划的步骤索引"""
        # 获取推理结果
        template = _env.from_string(GET_REPLAN_START_STEP_INDEX[language])
        prompt = template.render(
            goal=user_goal,
            error_message=error_message,
            current_plan=current_plan.model_dump(exclude_none=True, by_alias=True),
            history=history,
        )
        result = await MCPPlanner.get_resoning_result(prompt, reasoning_llm)
        # 解析为结构化数据
        schema = RestartStepIndex.model_json_schema()
        schema["properties"]["start_index"]["maximum"] = len(current_plan.plans) - 1
        schema["properties"]["start_index"]["minimum"] = 0
        restart_index = await MCPPlanner._parse_result(result, schema)
        # 使用RestartStepIndex模型解析结果
        return RestartStepIndex.model_validate(restart_index)

    @staticmethod
    async def create_plan(
        user_goal: str,
        is_replan: bool = False,
        error_message: str = "",
        current_plan: MCPPlan | None = None,
        tool_list: list[MCPTool] = [],
        max_steps: int = 6,
        reasoning_llm: ReasoningLLM = ReasoningLLM(),
        language: LanguageType = LanguageType.CHINESE,
    ) -> MCPPlan:
        """规划下一步的执行流程，并输出"""
        # 获取推理结果
        result = await MCPPlanner._get_reasoning_plan(
            user_goal, is_replan, error_message, current_plan, tool_list, max_steps, reasoning_llm, language
        )

        # 解析为结构化数据
        return await MCPPlanner._parse_plan_result(result, max_steps)

    @staticmethod
    async def _get_reasoning_plan(
        user_goal: str,
        is_replan: bool = False,
        error_message: str = "",
        current_plan: MCPPlan | None = None,
        tool_list: list[MCPTool] = [],
        max_steps: int = 10,
        reasoning_llm: ReasoningLLM = ReasoningLLM(),
        language: LanguageType = LanguageType.CHINESE,
    ) -> str:
        """获取推理大模型的结果"""
        # 格式化Prompt
        tool_ids = [tool.id for tool in tool_list]
        if is_replan:
            template = _env.from_string(RECREATE_PLAN[language])
            prompt = template.render(
                current_plan=current_plan.model_dump(exclude_none=True, by_alias=True),
                error_message=error_message,
                goal=user_goal,
                tools=tool_list,
                max_num=max_steps,
            )
        else:
            template = _env.from_string(CREATE_PLAN[language])
            prompt = template.render(
                goal=user_goal,
                tools=tool_list,
                max_num=max_steps,
            )
        return await MCPPlanner.get_resoning_result(prompt, reasoning_llm)

    @staticmethod
    async def _parse_plan_result(result: str, max_steps: int) -> MCPPlan:
        """将推理结果解析为结构化数据"""
        # 格式化Prompt
        schema = MCPPlan.model_json_schema()
        schema["properties"]["plans"]["maxItems"] = max_steps
        plan = await MCPPlanner._parse_result(result, schema)
        # 使用Function模型解析结果
        return MCPPlan.model_validate(plan)

    @staticmethod
    async def create_next_step(
        goal: str,
        history: str,
        tools: list[MCPTool],
        reasoning_llm: ReasoningLLM = ReasoningLLM(),
        language: LanguageType = LanguageType.CHINESE,
    ) -> Step:
        """创建下一步的执行步骤"""
        # 获取推理结果
        template = _env.from_string(GEN_STEP[language])
        prompt = template.render(goal=goal, history=history, tools=tools)
        result = await MCPPlanner.get_resoning_result(prompt, reasoning_llm)

        # 解析为结构化数据
        schema = Step.model_json_schema()
        if "enum" not in schema["properties"]["tool_id"]:
            schema["properties"]["tool_id"]["enum"] = []
        for tool in tools:
            schema["properties"]["tool_id"]["enum"].append(tool.id)
        step = await MCPPlanner._parse_result(result, schema)
        logger.info("[MCPPlanner] 创建下一步的执行步骤: %s", step)
        # 使用Step模型解析结果

        step = Step.model_validate(step)
        if len(step.description) > 15:
            # 限制步骤描述长度为15个字符
            step.description = step.description[:15]+'...'
        return step

    @staticmethod
    async def tool_skip(
        task: Task,
        step_id: str,
        step_name: str,
        step_instruction: str,
        step_content: str,
        reasoning_llm: ReasoningLLM = ReasoningLLM(),
        language: LanguageType = LanguageType.CHINESE,
    ) -> ToolSkip:
        """判断当前步骤是否需要跳过"""
        # 获取推理结果
        template = _env.from_string(TOOL_SKIP[language])
        from apps.scheduler.mcp_agent.host import MCPHost
        history = await MCPHost.assemble_memory(task)
        prompt = template.render(
            step_id=step_id,
            step_name=step_name,
            step_instruction=step_instruction,
            step_content=step_content,
            history=history,
            goal=task.runtime.question
        )
        result = await MCPPlanner.get_resoning_result(prompt, reasoning_llm)

        # 解析为结构化数据
        schema = ToolSkip.model_json_schema()
        skip_result = await MCPPlanner._parse_result(result, schema)
        # 使用ToolSkip模型解析结果
        return ToolSkip.model_validate(skip_result)

    @staticmethod
    async def get_tool_risk(
        tool: MCPTool,
        input_parm: dict[str, Any],
        additional_info: str = "",
        resoning_llm: ReasoningLLM = ReasoningLLM(),
        language: LanguageType = LanguageType.CHINESE,
    ) -> ToolRisk:
        """获取MCP工具的风险评估结果"""
        # 获取推理结果
        result = await MCPPlanner._get_reasoning_risk(
            tool, input_parm, additional_info, resoning_llm, language
        )

        # 返回风险评估结果
        return await MCPPlanner._parse_risk_result(result)

    @staticmethod
    async def _get_reasoning_risk(
        tool: MCPTool,
        input_param: dict[str, Any],
        additional_info: str,
        resoning_llm: ReasoningLLM,
        language: LanguageType = LanguageType.CHINESE,
    ) -> str:
        """获取推理大模型的风险评估结果"""
        template = _env.from_string(RISK_EVALUATE[language])
        prompt = template.render(
            tool_name=tool.name,
            tool_description=tool.description,
            input_param=input_param,
            additional_info=additional_info,
        )
        return await MCPPlanner.get_resoning_result(prompt, resoning_llm)

    @staticmethod
    async def _parse_risk_result(result: str) -> ToolRisk:
        """将推理结果解析为结构化数据"""
        schema = ToolRisk.model_json_schema()
        risk = await MCPPlanner._parse_result(result, schema)
        # 使用ToolRisk模型解析结果
        return ToolRisk.model_validate(risk)

    @staticmethod
    async def _get_reasoning_tool_execute_error_type(
        user_goal: str,
        current_plan: MCPPlan,
        tool: MCPTool,
        input_param: dict[str, Any],
        error_message: str,
        reasoning_llm: ReasoningLLM = ReasoningLLM(),
        language: LanguageType = LanguageType.CHINESE,
    ) -> str:
        """获取推理大模型的工具执行错误类型"""
        template = _env.from_string(TOOL_EXECUTE_ERROR_TYPE_ANALYSIS[language])
        prompt = template.render(
            goal=user_goal,
            current_plan=current_plan.model_dump(exclude_none=True, by_alias=True),
            tool_name=tool.name,
            tool_description=tool.description,
            input_param=input_param,
            error_message=error_message,
        )
        return await MCPPlanner.get_resoning_result(prompt, reasoning_llm)

    @staticmethod
    async def _parse_tool_execute_error_type_result(result: str) -> ToolExcutionErrorType:
        """将推理结果解析为工具执行错误类型"""
        schema = ToolExcutionErrorType.model_json_schema()
        error_type = await MCPPlanner._parse_result(result, schema)
        # 使用ToolExcutionErrorType模型解析结果
        return ToolExcutionErrorType.model_validate(error_type)

    @staticmethod
    async def get_tool_execute_error_type(
        user_goal: str,
        current_plan: MCPPlan,
        tool: MCPTool,
        input_param: dict[str, Any],
        error_message: str,
        reasoning_llm: ReasoningLLM = ReasoningLLM(),
        language: LanguageType = LanguageType.CHINESE,
    ) -> ToolExcutionErrorType:
        """获取MCP工具执行错误类型"""
        # 获取推理结果
        result = await MCPPlanner._get_reasoning_tool_execute_error_type(
            user_goal, current_plan, tool, input_param, error_message, reasoning_llm, language
        )
        # 返回工具执行错误类型
        return await MCPPlanner._parse_tool_execute_error_type_result(result)

    @staticmethod
    async def is_param_error(
        goal: str,
        history: str,
        error_message: str,
        tool: MCPTool,
        step_description: str,
        input_params: dict[str, Any],
        reasoning_llm: ReasoningLLM = ReasoningLLM(),
        language: LanguageType = LanguageType.CHINESE,
    ) -> IsParamError:
        """判断错误信息是否是参数错误"""
        tmplate = _env.from_string(IS_PARAM_ERROR[language])
        prompt = tmplate.render(
            goal=goal,
            history=history,
            step_id=tool.id,
            step_name=tool.name,
            step_description=step_description,
            input_params=input_params,
            error_message=error_message,
        )
        result = await MCPPlanner.get_resoning_result(prompt, reasoning_llm)
        # 解析为结构化数据
        schema = IsParamError.model_json_schema()
        is_param_error = await MCPPlanner._parse_result(result, schema)
        # 使用IsParamError模型解析结果
        return IsParamError.model_validate(is_param_error)

    @staticmethod
    async def change_err_message_to_description(
        error_message: str,
        tool: MCPTool,
        input_params: dict[str, Any],
        reasoning_llm: ReasoningLLM = ReasoningLLM(),
        language: LanguageType = LanguageType.CHINESE,
    ) -> str:
        """将错误信息转换为工具描述"""
        template = _env.from_string(CHANGE_ERROR_MESSAGE_TO_DESCRIPTION[language])
        prompt = template.render(
            error_message=error_message,
            tool_name=tool.name,
            tool_description=tool.description,
            input_schema=tool.input_schema,
            input_params=input_params,
        )
        result = await MCPPlanner.get_resoning_result(prompt, reasoning_llm)
        return result

    @staticmethod
    async def get_missing_param(
        tool: MCPTool,
        input_param: dict[str, Any],
        error_message: str,
        reasoning_llm: ReasoningLLM = ReasoningLLM(),
        language: LanguageType = LanguageType.CHINESE,
    ) -> list[str]:
        """获取缺失的参数"""
        slot = Slot(schema=tool.input_schema)
        template = _env.from_string(GET_MISSING_PARAMS[language])
        schema_with_null = slot.add_null_to_basic_types()
        prompt = template.render(
            tool_name=tool.name,
            tool_description=tool.description,
            input_param=input_param,
            schema=schema_with_null,
            error_message=error_message,
        )
        result = await MCPPlanner.get_resoning_result(prompt, reasoning_llm)
        # 解析为结构化数据
        input_param_with_null = await MCPPlanner._parse_result(result, schema_with_null)
        return input_param_with_null

    @staticmethod
    async def generate_answer(
        user_goal: str,
        memory: str,
        resoning_llm: ReasoningLLM = ReasoningLLM(),
        language: LanguageType = LanguageType.CHINESE,
    ) -> AsyncGenerator[str, None]:
        """生成最终回答"""
        template = _env.from_string(FINAL_ANSWER[language])
        prompt = template.render(
            memory=memory,
            goal=user_goal,
        )
        async for chunk in resoning_llm.call(
            [{"role": "user", "content": prompt}],
            streaming=True,
            temperature=0.07,
        ):
            yield chunk
