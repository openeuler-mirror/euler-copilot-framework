# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Agent执行器"""
from datetime import datetime, UTC
import logging
import uuid

import anyio
from mcp.types import TextContent
from pydantic import Field

from apps.services.llm import LLMManager
from apps.llm.reasoning import ReasoningLLM
from apps.llm.function import FunctionLLM
from apps.llm.enum import DefaultModelId
from apps.scheduler.executor.base import BaseExecutor
from apps.schemas.enum_var import LanguageType
from apps.scheduler.mcp_agent.host import MCPHost
from apps.scheduler.mcp_agent.plan import MCPPlanner
from apps.scheduler.mcp_agent.select import FINAL_TOOL_ID, SELF_DESC_TOOL_ID
from apps.scheduler.pool.mcp.pool import MCPPool
from apps.schemas.enum_var import EventType, FlowStatus, StepStatus
from apps.schemas.mcp import (
    MCPCollection,
    MCPTool,
    Step,
)
from apps.schemas.message import FlowParams
from apps.schemas.task import FlowStepHistory
from apps.schemas.config import LLMConfig
from apps.schemas.config import FunctionCallConfig
from apps.services.appcenter import AppCenterManager
from apps.services.mcp_service import MCPServiceManager
from apps.services.task import TaskManager
from apps.services.user import UserManager

logger = logging.getLogger(__name__)


class MCPAgentExecutor(BaseExecutor):
    """MCP Agent执行器"""

    max_steps: int = Field(default=40, description="最大步数")
    servers_id: list[str] = Field(description="MCP server id")
    agent_id: str = Field(default="", description="Agent ID")
    agent_description: str = Field(default="", description="Agent描述")
    mcp_list: list[MCPCollection] = Field(
        description="MCP服务器列表", default_factory=list)
    mcp_pool: MCPPool = Field(
        description="MCP池", default_factory=MCPPool, exclude=True)
    tools: dict[str, MCPTool] = Field(
        description="MCP工具列表，key为tool_id",
        default_factory=dict,
    )
    tool_list: list[MCPTool] = Field(
        description="MCP工具列表，包含所有MCP工具",
        default_factory=list,
    )
    params: FlowParams | bool | None = Field(
        default=None,
        description="流执行过程中的参数补充",
        alias="params",
    )
    chat_llm_id: str = Field(
        default=DefaultModelId.DEFAULT_CHAT_MODEL_ID.value,
        description="聊天大模型ID",
    )
    enable_thinking: bool = Field(default=False, description="是否启用思考模式")
    func_call_llm_id: str = Field(
        default=DefaultModelId.DEFAULT_FUNCTION_CALL_MODEL_ID.value,
        description="函数调用大模型ID",
    )
    resoning_llm: ReasoningLLM = Field(
        description="推理大模型",
        default_factory=ReasoningLLM,
        exclude=True
    )
    function_call_llm: FunctionLLM = Field(
        description="函数调用大模型",
        default_factory=FunctionLLM,
        exclude=True
    )
    app_owner: str = Field(default="", description="应用所有者")
    auto_execute: bool | None = Field(default=None, description="是否自动执行（来自请求）")
    mcp_host: MCPHost = Field(
        description="MCP主机",
        default_factory=MCPHost,
        exclude=True
    )
    mcp_planner: MCPPlanner = Field(
        description="MCP规划器",
        default_factory=MCPPlanner,
        exclude=True
    )

    async def init_llms(self) -> None:
        """初始化大模型"""
        reasoning_llm = await LLMManager.get_llm_by_id(self.chat_llm_id)
        reasoning_llm_config = LLMConfig(
            provider=reasoning_llm.provider,
            api_key=reasoning_llm.openai_api_key,
            endpoint=reasoning_llm.openai_base_url,
            model=reasoning_llm.model_name,
            max_tokens=reasoning_llm.max_tokens,
            temperature=0.7
        )
        self.resoning_llm = ReasoningLLM(config=reasoning_llm_config)
        function_call_llm = await LLMManager.get_llm_by_id(self.func_call_llm_id)
        function_call_llm_config = FunctionCallConfig(
            provider=function_call_llm.provider,
            api_key=function_call_llm.openai_api_key,
            endpoint=function_call_llm.openai_base_url,
            model=function_call_llm.model_name,
            max_tokens=function_call_llm.max_tokens,
            temperature=0.0
        )
        self.function_call_llm = FunctionLLM(config=function_call_llm_config)

    async def init_mcp_plan_and_host(self) -> None:
        """初始化MCP的Host和Planner"""
        self.mcp_host = MCPHost(
            reasoning_llm=self.resoning_llm,
            function_llm=self.function_call_llm,
        )
        self.mcp_planner = MCPPlanner(
            reasoning_llm=self.resoning_llm,
            function_llm=self.function_call_llm,
        )

    async def get_auto_execute(self) -> bool:
        """
        获取自动执行设置
        优先级：请求中的设置 > 用户全局设置
        """
        # 如果请求中明确指定了，使用请求中的设置
        if self.auto_execute is not None:
            return self.auto_execute

        # 否则使用用户的全局设置
        user_info = await UserManager.get_userinfo_by_user_sub(self.task.ids.user_sub)
        return user_info.auto_execute

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
            if self.app_owner not in mcp_service.activated:
                logger.warning("[MCPAgentExecutor] MCP服务 %s 未被应用所有者 %s 激活，跳过",
                               mcp_service.name, self.app_owner)
                continue
            # 尝试初始化MCP，只有成功才添加到列表
            client = await self.mcp_pool._init_mcp(mcp_id, self.app_owner)
            if client is None:
                logger.warning(
                    "[MCPAgentExecutor] MCP服务 %s 初始化失败，跳过", mcp_service.name)
                continue
            self.mcp_list.append(mcp_service)
            for tool in mcp_service.tools:
                self.tools[tool.id] = tool
            self.tool_list.extend(mcp_service.tools)
        if self.task.language == LanguageType.CHINESE:
            self.tools[FINAL_TOOL_ID] = MCPTool(
                id=FINAL_TOOL_ID, name="Final Tool", description="结束流程的工具", mcp_id="", input_schema={},
            )
            self.tool_list.append(
                MCPTool(id=FINAL_TOOL_ID, name="Final Tool",
                        description="结束流程的工具", mcp_id="", input_schema={}),
            )
            self.tools[SELF_DESC_TOOL_ID] = MCPTool(
                id=SELF_DESC_TOOL_ID,
                name="Self Description",
                description="用于描述自身能力和背景信息的工具",
                mcp_id="",
                input_schema={},
            )
            self.tool_list.append(
                MCPTool(
                    id=SELF_DESC_TOOL_ID,
                    name="Self Description",
                    description="用于描述自身能力和背景信息的工具",
                    mcp_id="",
                    input_schema={},
                )
            )
        else:
            self.tools[FINAL_TOOL_ID] = MCPTool(id=FINAL_TOOL_ID, name="Final Tool",
                                                description="The tool to end the process", mcp_id="", input_schema={},)
            self.tool_list.append(
                MCPTool(
                    id=FINAL_TOOL_ID, name="Final Tool", description="The tool to end the process",
                    mcp_id="", input_schema={}),)
            self.tools[SELF_DESC_TOOL_ID] = MCPTool(
                id=SELF_DESC_TOOL_ID,
                name="Self Description",
                description="A tool used to describe one's own abilities and background information",
                mcp_id="",
                input_schema={},
            )
            self.tool_list.append(
                MCPTool(
                    id=SELF_DESC_TOOL_ID,
                    name="Self Description",
                    description="A tool used to describe one's own abilities and background information",
                    mcp_id="",
                    input_schema={},
                )
            )

    async def get_tool_input_param(self, is_first: bool) -> None:
        # 工具的入参是 {} ，不需要填充
        if self.task.state.tool_id in [FINAL_TOOL_ID, SELF_DESC_TOOL_ID]:
            self.task.state.current_input = {}
            return
        if is_first:
            # 获取第一个输入参数
            mcp_tool = self.tools[self.task.state.tool_id]
            self.task.state.current_input = await self.mcp_host._get_first_input_params(
                mcp_tool, self.task.runtime.question, self.task.state.step_description, self.task, self.resoning_llm
            )
        else:
            # 获取后续输入参数
            if isinstance(self.params, FlowParams):
                params = self.params.content
                params_description = self.params.description
            else:
                params = {}
                params_description = ""
            mcp_tool = self.tools[self.task.state.tool_id]
            self.task.state.current_input = await self.mcp_host._fill_params(
                mcp_tool,
                self.task.runtime.question,
                self.task.state.step_description,
                self.task.state.current_input,
                self.task.state.error_message,
                params,
                params_description,
                self.task.language,
            )

    async def confirm_before_step(self) -> None:
        """确认前步骤"""
        # 发送确认消息
        mcp_tool = self.tools[self.task.state.tool_id]
        confirm_message = await self.mcp_planner.get_tool_risk(
            mcp_tool, self.task.state.current_input, "", self.resoning_llm, self.task.language
        )
        await self.update_tokens()
        await self.push_message(
            EventType.STEP_WAITING_FOR_START, confirm_message.model_dump(
                exclude_none=True, by_alias=True),
        )
        await self.push_message(EventType.FLOW_STOP, {})
        self.task.state.flow_status = FlowStatus.WAITING
        self.task.state.step_status = StepStatus.WAITING
        self.task.context.append(
            FlowStepHistory(
                task_id=self.task.id,
                step_id=self.task.state.step_id,
                step_name=self.task.state.step_name,
                step_description=self.task.state.step_description,
                step_status=self.task.state.step_status,
                flow_id=self.task.state.flow_id,
                flow_name=self.task.state.flow_name,
                flow_status=self.task.state.flow_status,
                input_data={},
                output_data={},
                ex_data=confirm_message.model_dump(
                    exclude_none=True, by_alias=True),
            )
        )

    async def run_step(self) -> None:
        """执行步骤"""
        self.task.state.flow_status = FlowStatus.RUNNING
        self.task.state.step_status = StepStatus.RUNNING
        mcp_tool = self.tools[self.task.state.tool_id]
        result_exchange = True
        try:
            if self.task.state.tool_id == SELF_DESC_TOOL_ID:
                tools = []
                for tool in self.tool_list:
                    if tool.id not in [SELF_DESC_TOOL_ID, FINAL_TOOL_ID]:
                        tools.append(f"{tool.name}: {tool.description}")
                output_params = {
                    "message": tools
                }
                result_exchange = False
            else:
                mcp_client = (await self.mcp_pool.get(mcp_tool.mcp_id, self.app_owner))
                if mcp_client is None:
                    error_msg = f"无法获取MCP服务 {mcp_tool.mcp_id} 的客户端，可能服务未正确初始化或已断开"
                    logger.error("[MCPAgentExecutor] %s", error_msg)
                    self.task.state.step_status = StepStatus.ERROR
                    self.task.state.error_message = error_msg
                    return
                output_params = await mcp_client.call_tool(mcp_tool.name, self.task.state.current_input)
        except anyio.ClosedResourceError:
            logger.exception(
                "[MCPAgentExecutor] MCP客户端连接已关闭: %s", mcp_tool.mcp_id)
            await self.mcp_pool.stop(mcp_tool.mcp_id, self.app_owner)
            await self.mcp_pool._init_mcp(mcp_tool.mcp_id, self.app_owner)
            self.task.state.step_status = StepStatus.ERROR
            return
        except Exception as e:
            import traceback
            logger.exception("[MCPAgentExecutor] 执行步骤 %s 时发生错误: %s",
                             mcp_tool.name, traceback.format_exc())
            self.task.state.step_status = StepStatus.ERROR
            self.task.state.error_message = str(e)
            return
        if result_exchange:
            if output_params.isError:
                err = ""
                for output in output_params.content:
                    if isinstance(output, TextContent):
                        err += output.text
                self.task.state.step_status = StepStatus.ERROR
                self.task.state.error_message = err
                return
            message = ""
            for output in output_params.content:
                if isinstance(output, TextContent):
                    message += output.text
            output_params = {
                "message": message,
            }

        await self.update_tokens()
        await self.push_message(EventType.STEP_INPUT, self.task.state.current_input)
        await self.push_message(EventType.STEP_OUTPUT, output_params)
        self.task.context.append(
            FlowStepHistory(
                task_id=self.task.id,
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

    async def generate_params_with_null(self) -> None:
        """生成参数补充"""
        mcp_tool = self.tools[self.task.state.tool_id]
        params_with_null = await self.mcp_planner.get_missing_param(
            mcp_tool,
            self.task.state.current_input,
            self.task.state.error_message,
            self.resoning_llm,
            self.task.language,
        )
        await self.update_tokens()
        error_message = await self.mcp_planner.change_err_message_to_description(
            error_message=self.task.state.error_message,
            tool=mcp_tool,
            input_params=self.task.state.current_input,
            reasoning_llm=self.resoning_llm,
            language=self.task.language,
        )
        await self.push_message(
            EventType.STEP_WAITING_FOR_PARAM, data={
                "message": error_message, "params": params_with_null}
        )
        await self.push_message(EventType.FLOW_STOP, data={})
        self.task.state.flow_status = FlowStatus.WAITING
        self.task.state.step_status = StepStatus.PARAM
        self.task.context.append(
            FlowStepHistory(
                task_id=self.task.id,
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
                    "message": error_message,
                    "params": params_with_null
                }
            )
        )

    async def get_next_step(self) -> None:
        """获取下一步"""
        self.task.tokens.time = datetime.now(UTC).timestamp()
        self.task.state.retry_times = 0
        if self.task.state.step_cnt < self.max_steps:
            self.task.state.step_cnt += 1
            history = await self.mcp_host.assemble_memory(self.task)
            max_retry = 3
            step = None
            for i in range(max_retry):
                try:
                    step = await self.mcp_planner.create_next_step(self.task.runtime.question, history, self.tool_list, self.resoning_llm, self.task.language)
                    if step.tool_id in self.tools.keys():
                        break
                except Exception as e:
                    logger.warning(
                        "[MCPAgentExecutor] 获取下一步失败，重试中: %s", str(e))
            if step is None or step.tool_id not in self.tools.keys():
                step = Step(
                    tool_id=FINAL_TOOL_ID,
                    description=FINAL_TOOL_ID
                )
            tool_id = step.tool_id
            if tool_id == FINAL_TOOL_ID:
                step_name = FINAL_TOOL_ID
            else:
                step_name = self.tools[tool_id].name
            step_description = step.description
            self.task.state.step_id = str(uuid.uuid4())
            self.task.state.tool_id = tool_id
            self.task.state.step_name = step_name
            self.task.state.step_description = step_description
            self.task.state.step_status = StepStatus.INIT
            self.task.state.current_input = {}
        else:
            # 没有下一步了，结束流程
            self.task.state.tool_id = FINAL_TOOL_ID
        return

    async def error_handle_after_step(self) -> None:
        """步骤执行失败后的错误处理"""
        self.task.state.step_status = StepStatus.ERROR
        self.task.state.flow_status = FlowStatus.ERROR
        await self.push_message(
            EventType.FLOW_FAILED,
            data={}
        )
        if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
            del self.task.context[-1]
        self.task.context.append(
            FlowStepHistory(
                task_id=self.task.id,
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
        self.task.state.tool_id = FINAL_TOOL_ID

    async def work(self) -> None:
        """执行当前步骤"""
        if self.task.state.step_status == StepStatus.INIT:
            await self.push_message(
                EventType.STEP_INIT,
                data={}
            )
            await self.get_tool_input_param(is_first=True)
            auto_execute = await self.get_auto_execute()
            if not auto_execute:
                # 等待用户确认
                await self.confirm_before_step()
                return
            self.task.state.step_status = StepStatus.RUNNING
        elif self.task.state.step_status in [StepStatus.PARAM, StepStatus.WAITING, StepStatus.RUNNING]:
            if self.task.state.step_status == StepStatus.PARAM:
                if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                    del self.task.context[-1]
                await self.get_tool_input_param(is_first=False)
            elif self.task.state.step_status == StepStatus.WAITING:
                if self.params:
                    if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                        del self.task.context[-1]
                else:
                    self.task.state.flow_status = FlowStatus.CANCELLED
                    self.task.state.step_status = StepStatus.CANCELLED
                    await self.push_message(
                        EventType.STEP_CANCEL,
                        data={}
                    )
                    await self.push_message(
                        EventType.FLOW_CANCEL,
                        data={}
                    )
                    if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                        self.task.context[-1].step_status = StepStatus.CANCELLED
                    return
            max_retry = 5
            for i in range(max_retry):
                if i != 0:
                    await self.get_tool_input_param(is_first=True)
                await self.run_step()
                if self.task.state.step_status == StepStatus.SUCCESS:
                    break
        elif self.task.state.step_status == StepStatus.ERROR:
            # 错误处理
            self.task.state.retry_times += 1
            if self.task.state.retry_times >= 3:
                await self.error_handle_after_step()
            else:
                auto_execute = await self.get_auto_execute()
                if auto_execute:
                    await self.push_message(
                        EventType.STEP_ERROR,
                        data={
                            "message": self.task.state.error_message,
                        }
                    )
                    if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                        self.task.context[-1].step_status = StepStatus.ERROR
                        self.task.context[-1].output_data = {
                            "message": self.task.state.error_message,
                        }
                    else:
                        self.task.context.append(
                            FlowStepHistory(
                                task_id=self.task.id,
                                step_id=self.task.state.step_id,
                                step_name=self.task.state.step_name,
                                step_description=self.task.state.step_description,
                                step_status=StepStatus.ERROR,
                                flow_id=self.task.state.flow_id,
                                flow_name=self.task.state.flow_name,
                                flow_status=self.task.state.flow_status,
                                input_data=self.task.state.current_input,
                                output_data={
                                    "message": self.task.state.error_message,
                                },
                            )
                        )
                    await self.get_next_step()
                else:
                    mcp_tool = self.tools[self.task.state.tool_id]
                    is_param_error = await self.mcp_planner.is_param_error(
                        self.task.runtime.question,
                        await self.mcp_host.assemble_memory(self.task),
                        self.task.state.error_message,
                        mcp_tool,
                        self.task.state.step_description,
                        self.task.state.current_input,
                        self.resoning_llm,
                        self.task.language
                    )
                    if is_param_error.is_param_error:
                        # 如果是参数错误，生成参数补充
                        await self.generate_params_with_null()
                    else:
                        await self.push_message(
                            EventType.STEP_ERROR,
                            data={
                                "message": self.task.state.error_message,
                            }
                        )
                        if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                            self.task.context[-1].step_status = StepStatus.ERROR
                            self.task.context[-1].output_data = {
                                "message": self.task.state.error_message,
                            }
                        else:
                            self.task.context.append(
                                FlowStepHistory(
                                    task_id=self.task.id,
                                    step_id=self.task.state.step_id,
                                    step_name=self.task.state.step_name,
                                    step_description=self.task.state.step_description,
                                    step_status=StepStatus.ERROR,
                                    flow_id=self.task.state.flow_id,
                                    flow_name=self.task.state.flow_name,
                                    flow_status=self.task.state.flow_status,
                                    input_data=self.task.state.current_input,
                                    output_data={
                                        "message": self.task.state.error_message,
                                    },
                                )
                            )
                        await self.get_next_step()
        elif self.task.state.step_status == StepStatus.SUCCESS:
            await self.get_next_step()

    async def summarize(self) -> None:
        """总结"""
        async for chunk in self.mcp_planner.generate_answer(
            self.task.runtime.question,
            (await self.mcp_host.assemble_memory(self.task)),
            self.resoning_llm,
            self.task.language,
            enable_thinking=self.enable_thinking
        ):
            await self.push_message(
                EventType.TEXT_ADD,
                data=chunk
            )
            self.task.runtime.answer += chunk

    async def run(self) -> None:
        """执行MCP Agent的主逻辑"""
        # 初始化MCP服务
        await self.init_llms()
        await self.init_mcp_plan_and_host()
        self.app_owner = (await AppCenterManager.fetch_app_data_by_id(self.agent_id)).author
        await self.load_state()
        await self.load_mcp()
        data = {}
        if self.task.state.flow_status == FlowStatus.INIT:
            # 初始化状态
            try:
                self.task.state.flow_id = str(uuid.uuid4())
                self.task.state.flow_name = (await self.mcp_planner.get_flow_name(
                    self.task.runtime.question, self.resoning_llm, self.task.language
                )).flow_name
                flow_risk = await self.mcp_planner.get_flow_excute_risk(
                    self.task.runtime.question, self.tool_list, self.resoning_llm, self.task.language
                )
                auto_execute = await self.get_auto_execute()
                if auto_execute:
                    data = flow_risk.model_dump(
                        exclude_none=True, by_alias=True)
                await TaskManager.save_task(self.task.id, self.task)
                await self.get_next_step()
            except Exception as e:
                logger.exception("[MCPAgentExecutor] 初始化失败")
                self.task.state.flow_status = FlowStatus.ERROR
                self.task.state.error_message = str(e)
                await self.push_message(
                    EventType.FLOW_FAILED,
                    data={}
                )
                return
        self.task.state.flow_status = FlowStatus.RUNNING
        await self.push_message(
            EventType.FLOW_START,
            data=data
        )
        if self.task.state.tool_id == FINAL_TOOL_ID:
            # 如果已经是最后一步，直接结束
            self.task.state.flow_status = FlowStatus.SUCCESS
            await self.push_message(
                EventType.FLOW_SUCCESS,
                data={}
            )
            await self.summarize()
            return
        try:
            while self.task.state.flow_status == FlowStatus.RUNNING:
                if self.task.state.tool_id == FINAL_TOOL_ID:
                    break
                await self.work()
                await TaskManager.save_task(self.task.id, self.task)
            tool_id = self.task.state.tool_id
            if tool_id == FINAL_TOOL_ID:
                # 如果已经是最后一步，直接结束
                self.task.state.flow_status = FlowStatus.SUCCESS
                self.task.state.step_status = StepStatus.SUCCESS
                await self.push_message(
                    EventType.FLOW_SUCCESS,
                    data={}
                )
                await self.summarize()
        except Exception as e:
            logger.exception("[MCPAgentExecutor] 执行过程中发生错误")
            self.task.state.flow_status = FlowStatus.ERROR
            self.task.state.error_message = str(e)
            self.task.state.step_status = StepStatus.ERROR
            await self.push_message(
                EventType.STEP_ERROR,
                data={}
            )
            await self.push_message(
                EventType.FLOW_FAILED,
                data={}
            )
            if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                del self.task.context[-1]
            self.task.context.append(
                FlowStepHistory(
                    task_id=self.task.id,
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
            for mcp_service in self.mcp_list:
                try:
                    await self.mcp_pool.stop(mcp_service.id, self.app_owner)
                except Exception as e:
                    import traceback
                    logger.error(
                        "[MCPAgentExecutor] 停止MCP客户端时发生错误: %s", traceback.format_exc())
