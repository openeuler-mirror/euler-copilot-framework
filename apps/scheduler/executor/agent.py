# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Agent执行器"""

import logging
import uuid
from pydantic import Field
from typing import Any
from apps.llm.patterns.rewrite import QuestionRewrite
from apps.llm.reasoning import ReasoningLLM
from apps.scheduler.executor.base import BaseExecutor
from apps.schemas.enum_var import EventType, SpecialCallType, FlowStatus, StepStatus
from apps.scheduler.mcp_agent.host import MCPHost
from apps.scheduler.mcp_agent.plan import MCPPlanner
from apps.scheduler.mcp_agent.select import FINAL_TOOL_ID, MCPSelector
from apps.scheduler.pool.mcp.client import MCPClient
from apps.schemas.mcp import (
    GoalEvaluationResult,
    RestartStepIndex,
    ToolRisk,
    ErrorType,
    ToolExcutionErrorType,
    MCPPlan,
    MCPCollection,
    MCPTool
)
from apps.schemas.task import ExecutorState, FlowStepHistory, StepQueueItem
from apps.schemas.message import param
from apps.services.task import TaskManager
from apps.services.appcenter import AppCenterManager
from apps.services.mcp_service import MCPServiceManager
from apps.services.user import UserManager
logger = logging.getLogger(__name__)


class MCPAgentExecutor(BaseExecutor):
    """MCP Agent执行器"""

    max_steps: int = Field(default=20, description="最大步数")
    servers_id: list[str] = Field(description="MCP server id")
    agent_id: str = Field(default="", description="Agent ID")
    agent_description: str = Field(default="", description="Agent描述")
    mcp_list: list[MCPCollection] = Field(description="MCP服务器列表", default=[])
    mcp_client: dict[str, MCPClient] = Field(
        description="MCP客户端列表，key为mcp_id", default={}
    )
    tools: dict[str, MCPTool] = Field(
        description="MCP工具列表，key为tool_id", default={}
    )
    params: param | bool | None = Field(
        default=None, description="流执行过程中的参数补充", alias="params"
    )
    resoning_llm: ReasoningLLM = Field(
        default=ReasoningLLM(),
        description="推理大模型",
    )

    async def update_tokens(self) -> None:
        """更新令牌数"""
        self.task.tokens.input_tokens = self.resoning_llm.input_tokens
        self.task.tokens.output_tokens = self.resoning_llm.output_tokens
        await TaskManager.save_task(self.task.id, self.task)

    async def load_state(self) -> None:
        """从数据库中加载FlowExecutor的状态"""
        logger.info("[FlowExecutor] 加载Executor状态")
        # 尝试恢复State
        if self.task.state and self.task.state.flow_status != FlowStatus.INIT:
            self.task.context = await TaskManager.get_context_by_task_id(self.task.id)

    async def load_mcp(self) -> None:
        """加载MCP服务器列表"""
        logger.info("[MCPAgentExecutor] 加载MCP服务器列表")
        # 获取MCP服务器列表
        app = await AppCenterManager.fetch_app_data_by_id(self.agent_id)
        mcp_ids = app.mcp_service
        for mcp_id in mcp_ids:
            mcp_service = await MCPServiceManager.get_mcp_service(mcp_id)
            if self.task.ids.user_sub not in mcp_service.activated:
                logger.warning(
                    "[MCPAgentExecutor] 用户 %s 未启用MCP %s",
                    self.task.ids.user_sub,
                    mcp_id,
                )
                continue

            self.mcp_list.append(mcp_service)
            self.mcp_client[mcp_id] = await MCPHost.get_client(self.task.ids.user_sub, mcp_id)
            for tool in mcp_service.tools:
                self.tools[tool.id] = tool

    async def plan(self, is_replan: bool = False, start_index: int | None = None) -> None:
        if is_replan:
            error_message = "之前的计划遇到以下报错\n\n"+self.task.state.error_message
        else:
            error_message = "初始化计划"
        tools = MCPSelector.select_top_tool(
            self.task.runtime.question, list(self.tools.values()),
            additional_info=error_message, top_n=40)
        if is_replan:
            logger.info("[MCPAgentExecutor] 重新规划流程")
            if not start_index:
                start_index = await MCPPlanner.get_replan_start_step_index(self.task.runtime.question,
                                                                           self.task.state.error_message,
                                                                           self.task.runtime.temporary_plans,
                                                                           self.resoning_llm)
            current_plan = self.task.runtime.temporary_plans.plans[start_index:]
            error_message = self.task.state.error_message
            temporary_plans = await MCPPlanner.create_plan(self.task.runtime.question,
                                                           is_replan=is_replan,
                                                           error_message=error_message,
                                                           current_plan=current_plan,
                                                           tool_list=tools,
                                                           max_steps=self.max_steps-start_index-1,
                                                           reasoning_llm=self.resoning_llm
                                                           )
            self.update_tokens()
            self.push_message(
                EventType.STEP_CANCEL,
                data={}
            )
            if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                self.task.context[-1].step_status = StepStatus.CANCELLED
            self.task.runtime.temporary_plans = self.task.runtime.temporary_plans.plans[:start_index] + temporary_plans.plans
            self.task.state.step_index = start_index
        else:
            start_index = 0
            self.task.runtime.temporary_plans = await MCPPlanner.create_plan(self.task.runtime.question, tool_list=tools, max_steps=self.max_steps, reasoning_llm=self.resoning_llm)
        for i in range(start_index, len(self.task.runtime.temporary_plans.plans)):
            self.task.runtime.temporary_plans.plans[i].step_id = str(uuid.uuid4())

    async def get_tool_input_param(self, is_first: bool) -> None:
        if is_first:
            # 获取第一个输入参数
            self.task.state.current_input = await MCPHost._get_first_input_params(self.tools[self.task.state.step_id], self.task.runtime.question, self.task)
        else:
            # 获取后续输入参数
            if isinstance(self.params, param):
                params = self.params.content
                params_description = self.params.description
            else:
                params = {}
                params_description = ""
            self.task.state.current_input = await MCPHost._fill_params(self.tools[self.task.state.step_id], self.task.state.current_input, self.task.state.error_message, params, params_description)

    async def reset_step_to_index(self, start_index: int) -> None:
        """重置步骤到开始"""
        logger.info("[MCPAgentExecutor] 重置步骤到索引 %d", start_index)
        if self.task.runtime.temporary_plans:
            self.task.state.flow_status = FlowStatus.RUNNING
            self.task.state.step_id = self.task.runtime.temporary_plans.plans[start_index].step_id
            self.task.state.step_index = 0
            self.task.state.step_name = self.task.runtime.temporary_plans.plans[start_index].tool
            self.task.state.step_description = self.task.runtime.temporary_plans.plans[start_index].content
            self.task.state.step_status = StepStatus.RUNNING
            self.task.state.retry_times = 0
        else:
            self.task.state.flow_status = FlowStatus.SUCCESS
            self.task.state.step_id = FINAL_TOOL_ID

    async def confirm_before_step(self) -> None:
        logger.info("[MCPAgentExecutor] 等待用户确认步骤 %d", self.task.state.step_index)
        # 发送确认消息
        confirm_message = await MCPPlanner.get_tool_risk(self.tools[self.task.state.step_id], self.task.state.current_input, "", self.resoning_llm)
        self.update_tokens()
        self.push_message(EventType.STEP_WAITING_FOR_START, confirm_message.model_dump(
            exclude_none=True, by_alias=True))
        self.push_message(EventType.FLOW_STOP, {})
        self.task.state.flow_status = FlowStatus.WAITING
        self.task.state.step_status = StepStatus.WAITING
        self.task.context.append(
            FlowStepHistory(
                step_id=self.task.state.step_id,
                step_name=self.task.state.step_name,
                step_description=self.task.state.step_description,
                step_status=self.task.state.step_status,
                flow_id=self.task.state.flow_id,
                flow_name=self.task.state.flow_name,
                flow_status=self.task.state.flow_status,
                input_data={},
                output_data={},
                ex_data=confirm_message.model_dump(exclude_none=True, by_alias=True),
            )
        )

    async def run_step(self):
        """执行步骤"""
        self.task.state.flow_status = FlowStatus.RUNNING
        self.task.state.step_status = StepStatus.RUNNING
        logger.info("[MCPAgentExecutor] 执行步骤 %d", self.task.state.step_index)
        # 获取MCP客户端
        mcp_tool = self.tools[self.task.state.step_id]
        mcp_client = self.mcp_client[mcp_tool.mcp_id]
        if not mcp_client:
            logger.error("[MCPAgentExecutor] MCP客户端未找到: %s", mcp_tool.mcp_id)
            self.task.state.flow_status = FlowStatus.ERROR
            error = "[MCPAgentExecutor] MCP客户端未找到: {}".format(mcp_tool.mcp_id)
            self.task.state.error_message = error
        try:
            output_params = await mcp_client.call_tool(mcp_tool.name, self.task.state.current_input)
            self.update_tokens()
            self.push_message(
                EventType.STEP_INPUT,
                self.task.state.current_input
            )
            self.push_message(
                EventType.STEP_OUTPUT,
                output_params
            )
            self.task.context.append(
                FlowStepHistory(
                    step_id=self.task.state.step_id,
                    step_name=self.task.state.step_name,
                    step_description=self.task.state.step_description,
                    step_status=StepStatus.SUCCESS,
                    flow_id=self.task.state.flow_id,
                    flow_name=self.task.state.flow_name,
                    flow_status=self.task.state.flow_status,
                    input_data=self.task.state.current_input,
                    output_data=output_params,
                )
            )
            self.task.state.step_status = StepStatus.SUCCESS
        except Exception as e:
            logger.warning("[MCPAgentExecutor] 执行步骤 %s 失败: %s", mcp_tool.name, str(e))
            import traceback
            self.task.state.error_message = traceback.format_exc()
            self.task.state.step_status = StepStatus.ERROR

    async def generate_params_with_null(self) -> None:
        """生成参数补充"""
        mcp_tool = self.tools[self.task.state.step_id]
        params_with_null = await MCPPlanner.get_missing_param(
            mcp_tool,
            self.task.state.current_input,
            self.task.state.error_message,
            self.resoning_llm
        )
        self.update_tokens()
        self.push_message(
            EventType.STEP_WAITING_FOR_PARAM,
            data={
                "message": "当运行产生如下报错：\n" + self.task.state.error_message,
                "params": params_with_null
            }
        )
        self.push_message(
            EventType.FLOW_STOP,
            data={}
        )
        self.task.state.flow_status = FlowStatus.WAITING
        self.task.state.step_status = StepStatus.PARAM
        self.task.context.append(
            FlowStepHistory(
                step_id=self.task.state.step_id,
                step_name=self.task.state.step_name,
                step_description=self.task.state.step_description,
                step_status=self.task.state.step_status,
                flow_id=self.task.state.flow_id,
                flow_name=self.task.state.flow_name,
                flow_status=self.task.state.flow_status,
                input_data={},
                output_data={},
                ex_data={
                    "message": "当运行产生如下报错：\n" + self.task.state.error_message,
                    "params": params_with_null
                }
            )
        )

    async def get_next_step(self) -> None:
        self.task.state.step_index += 1
        if self.task.state.step_index < len(self.task.runtime.temporary_plans):
            if self.task.runtime.temporary_plans.plans[self.task.state.step_index].step_id == FINAL_TOOL_ID:
                # 最后一步
                self.task.state.flow_status = FlowStatus.SUCCESS
                self.task.state.step_status = StepStatus.SUCCESS
                self.push_message(
                    EventType.FLOW_SUCCESS,
                    data={}
                )
                return
            self.task.state.step_id = self.task.runtime.temporary_plans.plans[self.task.state.step_index].step_id
            self.task.state.step_name = self.task.runtime.temporary_plans.plans[self.task.state.step_index].tool
            self.task.state.step_description = self.task.runtime.temporary_plans.plans[self.task.state.step_index].content
            self.task.state.step_status = StepStatus.INIT
            self.task.state.current_input = {}
            self.push_message(
                EventType.STEP_INIT,
                data={}
            )
        else:
            # 没有下一步了，结束流程
            self.task.state.flow_status = FlowStatus.SUCCESS
            self.task.state.step_status = StepStatus.SUCCESS
            self.push_message(
                EventType.FLOW_SUCCESS,
                data={}
            )
            return

    async def error_handle_after_step(self) -> None:
        """步骤执行失败后的错误处理"""
        self.task.state.step_status = StepStatus.ERROR
        self.task.state.flow_status = FlowStatus.ERROR
        self.push_message(
            EventType.FLOW_FAILED,
            data={}
        )
        if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
            del self.task.context[-1]
        self.task.context.append(
            FlowStepHistory(
                step_id=self.task.state.step_id,
                step_name=self.task.state.step_name,
                step_description=self.task.state.step_description,
                step_status=self.task.state.step_status,
                flow_id=self.task.state.flow_id,
                flow_name=self.task.state.flow_name,
                flow_status=self.task.state.flow_status,
                input_data={},
                output_data={},
            )
        )

    async def work(self) -> None:
        """执行当前步骤"""
        if self.task.state.step_status == StepStatus.INIT:
            await self.get_tool_input_param(is_first=True)
            user_info = await UserManager.get_userinfo_by_user_sub(self.task.ids.user_sub)
            if not user_info.auto_execute:
                # 等待用户确认
                await self.confirm_before_step()
                return
            self.task.state.step_status = StepStatus.RUNNING
        elif self.task.state.step_status in [StepStatus.PARAM, StepStatus.WAITING, StepStatus.RUNNING]:
            if self.task.context[-1].step_status == StepStatus.PARAM:
                if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                    del self.task.context[-1]
            elif self.task.state.step_status == StepStatus.WAITING:
                if self.params.content:
                    if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                        del self.task.context[-1]
                else:
                    self.task.state.flow_status = FlowStatus.CANCELLED
                    self.task.state.step_status = StepStatus.CANCELLED
                    self.push_message(
                        EventType.STEP_CANCEL,
                        data={}
                    )
                    self.push_message(
                        EventType.FLOW_CANCEL,
                        data={}
                    )
                    if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                        self.task.context[-1].step_status = StepStatus.CANCELLED
            if self.task.state.step_status == StepStatus.PARAM:
                await self.get_tool_input_param(is_first=False)
            max_retry = 5
            for i in range(max_retry):
                if i != 0:
                    await self.get_tool_input_param(is_first=False)
                await self.run_step()
                if self.task.state.step_status == StepStatus.SUCCESS:
                    break
        elif self.task.state.step_status == StepStatus.ERROR:
            # 错误处理
            if self.task.state.retry_times >= 3:
                await self.error_handle_after_step()
            else:
                user_info = await UserManager.get_userinfo_by_user_sub(self.task.ids.user_sub)
                mcp_tool = self.tools[self.task.state.step_id]
                error_type = await MCPPlanner.get_tool_execute_error_type(
                    self.task.runtime.question,
                    self.task.runtime.temporary_plans,
                    mcp_tool,
                    self.task.state.current_input,
                    self.task.state.error_message,
                    self.resoning_llm
                )
                if error_type.type == ErrorType.DECORRECT_PLAN or user_info.auto_execute:
                    await self.plan(is_replan=True)
                    self.reset_step_to_index(self.task.state.step_index)
                elif error_type.type == ErrorType.MISSING_PARAM:
                    await self.generate_params_with_null()
        elif self.task.state.step_status == StepStatus.SUCCESS:
            await self.get_next_step()

    async def summarize(self) -> None:
        async for chunk in MCPPlanner.generate_answer(
            self.task.runtime.question,
            self.task.runtime.temporary_plans,
            (await MCPHost.assemble_memory(self.task)),
            self.resoning_llm
        ):
            self.push_message(
                EventType.TEXT_ADD,
                data=chunk
            )
            self.task.runtime.answer += chunk

    async def run(self) -> None:
        """执行MCP Agent的主逻辑"""
        # 初始化MCP服务
        self.load_state()
        self.load_mcp()
        if self.task.state.flow_status == FlowStatus.INIT:
            # 初始化状态
            try:
                self.task.state.flow_id = str(uuid.uuid4())
                self.task.state.flow_name = await MCPPlanner.get_flow_name(self.task.runtime.question, self.resoning_llm)
                await self.plan(is_replan=False)
                self.reset_step_to_index(0)
                TaskManager.save_task(self.task.id, self.task)
            except Exception as e:
                logger.error("[MCPAgentExecutor] 初始化失败: %s", str(e))
                self.task.state.flow_status = FlowStatus.ERROR
                self.task.state.error_message = str(e)
                self.push_message(
                    EventType.FLOW_FAILED,
                    data={}
                )
                return
        self.task.state.flow_status = FlowStatus.RUNNING
        self.push_message(
            EventType.FLOW_START,
            data={}
        )
        try:
            while self.task.state.step_index < len(self.task.runtime.temporary_plans) and \
                    self.task.state.flow_status == FlowStatus.RUNNING:
                await self.work()
                TaskManager.save_task(self.task.id, self.task)
        except Exception as e:
            logger.error("[MCPAgentExecutor] 执行过程中发生错误: %s", str(e))
            self.task.state.flow_status = FlowStatus.ERROR
            self.task.state.error_message = str(e)
            self.task.state.step_status = StepStatus.ERROR
            self.push_message(
                EventType.STEP_ERROR,
                data={}
            )
            self.push_message(
                EventType.FLOW_FAILED,
                data={}
            )
            if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                del self.task.context[-1]
            self.task.context.append(
                FlowStepHistory(
                    step_id=self.task.state.step_id,
                    step_name=self.task.state.step_name,
                    step_description=self.task.state.step_description,
                    step_status=self.task.state.step_status,
                    flow_id=self.task.state.flow_id,
                    flow_name=self.task.state.flow_name,
                    flow_status=self.task.state.flow_status,
                    input_data={},
                    output_data={},
                )
            )
        finally:
            for client in self.mcp_client.values():
                await client.stop()
