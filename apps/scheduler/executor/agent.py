# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Agent执行器"""

import logging
import uuid
from typing import TYPE_CHECKING, cast

import anyio
from mcp.types import TextContent
from pydantic import Field

from apps.constants import AGENT_FINAL_STEP_NAME, AGENT_MAX_RETRY_TIMES, AGENT_MAX_STEPS
from apps.models import ExecutorHistory, ExecutorStatus, MCPTools, StepStatus
from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.mcp_agent.host import MCPHost
from apps.scheduler.mcp_agent.plan import MCPPlanner
from apps.scheduler.pool.mcp.pool import mcp_pool
from apps.schemas.agent import AgentAppMetadata
from apps.schemas.enum_var import EventType
from apps.schemas.mcp import Step
from apps.schemas.message import FlowParams
from apps.services.appcenter import AppCenterManager
from apps.services.mcp_service import MCPServiceManager
from apps.services.user import UserManager

if TYPE_CHECKING:
    from apps.models.task import ExecutorCheckpoint

_logger = logging.getLogger(__name__)

class MCPAgentExecutor(BaseExecutor):
    """MCP Agent执行器"""

    agent_id: uuid.UUID = Field(default=uuid.uuid4(), description="App ID作为Agent ID")
    agent_description: str = Field(default="", description="Agent描述")
    tools: dict[str, MCPTools] = Field(
        description="MCP工具列表，key为tool_id",
        default={},
    )
    params: FlowParams | bool | None = Field(
        default=None,
        description="流执行过程中的参数补充",
        alias="params",
    )

    async def init(self) -> None:
        """初始化MCP Agent"""
        # 初始化必要变量
        self._step_cnt = 0
        self._retry_times = 0
        self._mcp_list = []
        self._current_input = {}
        self._current_tool = None
        # 初始化MCP Host相关对象
        self._planner = MCPPlanner(self.task, self.llm)
        self._host = MCPHost(self.task, self.llm)
        user = await UserManager.get_user(self.task.metadata.userId)
        if not user:
            err = "[MCPAgentExecutor] 用户不存在: %s"
            _logger.error(err)
            raise RuntimeError(err)
        self._user = user
        # 获取历史
        await self._load_history()

    async def load_mcp(self) -> None:
        """加载MCP服务器列表"""
        _logger.info("[MCPAgentExecutor] 加载MCP服务器列表")
        # 获取MCP服务器列表
        app_metadata = await AppCenterManager.fetch_app_metadata_by_id(self.agent_id)
        if not isinstance(app_metadata, AgentAppMetadata):
            err = "[MCPAgentExecutor] 应用类型不是Agent"
            _logger.error(err)
            raise TypeError(err)

        mcp_ids = app_metadata.mcp_service
        for mcp_id in mcp_ids:
            if not await MCPServiceManager.is_user_actived(self.task.metadata.userId, mcp_id):
                _logger.warning(
                    "[MCPAgentExecutor] 用户 %s 未启用MCP %s",
                    self.task.metadata.userId,
                    mcp_id,
                )
                continue

            mcp_service = await MCPServiceManager.get_mcp_service(mcp_id)
            if mcp_service:
                self._mcp_list.append(mcp_service)

                for tool in await MCPServiceManager.get_mcp_tools(mcp_id):
                    self.tools[tool.id] = tool

        self.tools[AGENT_FINAL_STEP_NAME] = MCPTools(
            mcpId="", toolName=AGENT_FINAL_STEP_NAME, description="结束流程的工具",
            inputSchema={}, outputSchema={},
        )

    def _validate_task_state(self) -> None:
        """验证任务状态是否存在"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

    async def get_tool_input_param(self, *, is_first: bool) -> None:
        """获取工具输入参数"""
        self._validate_task_state()
        state = cast("ExecutorCheckpoint", self.task.state)

        if is_first:
            # 获取第一个输入参数
            self._current_tool = self.tools[state.stepName]
            self._current_input = await self._host.get_first_input_params(
                self._current_tool, self.task.runtime.userInput, self.task,
            )
        else:
            # 获取后续输入参数
            if isinstance(self.params, FlowParams):
                params = self.params.content
                params_description = self.params.description
            else:
                params = {}
                params_description = ""
            self._current_tool = self.tools[state.stepName]
            state.currentInput = await self._host.fill_params(
                self._current_tool,
                self.task.runtime.userInput,
                state.currentInput,
                state.errorMessage,
                params,
                params_description,
                self.task.runtime.language,
            )
        self.task.state = state

    def _validate_current_tool(self) -> None:
        """验证当前工具是否存在"""
        if self._current_tool is None:
            err = "[MCPAgentExecutor] 当前工具不存在"
            _logger.error(err)
            raise RuntimeError(err)

    def _get_error_message_str(self, error_message: dict | str | None) -> str:
        """将错误消息转换为字符串"""
        if isinstance(error_message, dict):
            return str(error_message.get("err_msg", ""))
        return str(error_message) if error_message else ""

    def _update_last_context_status(self, step_status: StepStatus, output_data: dict | None = None) -> None:
        """更新最后一个context的状态(如果是当前步骤)"""
        self._validate_task_state()
        state = cast("ExecutorCheckpoint", self.task.state)
        if len(self.task.context) and self.task.context[-1].stepId == state.stepId:
            self.task.context[-1].stepStatus = step_status
            if output_data is not None:
                self.task.context[-1].outputData = output_data

    async def _add_error_to_context(self, step_status: StepStatus) -> None:
        """添加错误到context,先移除重复的步骤再添加"""
        self._remove_last_context_if_same_step()
        self.task.context.append(
            self._create_executor_history(step_status=step_status),
        )

    async def _handle_final_step(self) -> None:
        """处理最终步骤,设置状态并总结"""
        self._validate_task_state()
        state = cast("ExecutorCheckpoint", self.task.state)
        state.executorStatus = ExecutorStatus.SUCCESS
        state.stepStatus = StepStatus.SUCCESS
        self.task.state = state
        await self._push_message(EventType.EXECUTOR_STOP, data={})
        await self.summarize()

    def _create_executor_history(
        self,
        step_status: StepStatus,
        input_data: dict | None = None,
        output_data: dict | None = None,
        extra_data: dict | None = None,
    ) -> ExecutorHistory:
        """创建ExecutorHistory对象"""
        self._validate_task_state()
        state = cast("ExecutorCheckpoint", self.task.state)
        current_tool = cast("MCPTools", self._current_tool)
        return ExecutorHistory(
            taskId=self.task.metadata.id,
            stepId=state.stepId,
            stepName=current_tool.toolName if self._current_tool else state.stepName,
            stepType=str(current_tool.id) if self._current_tool else "",
            stepStatus=step_status,
            executorId=state.executorId,
            executorName=state.executorName,
            executorStatus=state.executorStatus,
            inputData=input_data or {},
            outputData=output_data or {},
            extraData=extra_data or {},
        )

    def _remove_last_context_if_same_step(self) -> None:
        """如果最后一个context是当前步骤，则删除它"""
        self._validate_task_state()
        state = cast("ExecutorCheckpoint", self.task.state)
        if len(self.task.context) and self.task.context[-1].stepId == state.stepId:
            del self.task.context[-1]

    async def _handle_step_error_and_continue(self) -> None:
        """处理步骤错误并继续下一步"""
        self._validate_task_state()
        state = cast("ExecutorCheckpoint", self.task.state)
        error_output = {"message": state.errorMessage}

        # 先更新stepStatus
        state.stepStatus = StepStatus.ERROR
        self.task.state = state

        await self._push_message(
            EventType.STEP_END,
            data=error_output,
        )

        # 更新或添加错误到context
        if len(self.task.context) and self.task.context[-1].stepId == state.stepId:
            self._update_last_context_status(StepStatus.ERROR, error_output)
        else:
            self.task.context.append(
                self._create_executor_history(
                    step_status=StepStatus.ERROR,
                    input_data=self._current_input,
                    output_data=error_output,
                ),
            )
        await self.get_next_step()

    async def confirm_before_step(self) -> None:
        """确认前步骤"""
        self._validate_task_state()
        self._validate_current_tool()
        state = cast("ExecutorCheckpoint", self.task.state)
        current_tool = cast("MCPTools", self._current_tool)

        confirm_message = await self._planner.get_tool_risk(current_tool, self._current_input, "")

        # 先更新状态
        state.executorStatus = ExecutorStatus.WAITING
        state.stepStatus = StepStatus.WAITING
        self.task.state = state

        await self._push_message(
            EventType.STEP_WAITING_FOR_START, confirm_message.model_dump(exclude_none=True, by_alias=True),
        )
        self.task.context.append(
            self._create_executor_history(
                step_status=state.stepStatus,
                extra_data=confirm_message.model_dump(exclude_none=True, by_alias=True),
            ),
        )

    async def run_step(self) -> None:
        """执行步骤"""
        self._validate_task_state()
        state = cast("ExecutorCheckpoint", self.task.state)
        state.executorStatus = ExecutorStatus.RUNNING
        state.stepStatus = StepStatus.RUNNING
        self.task.state = state
        self._validate_current_tool()
        current_tool = cast("MCPTools", self._current_tool)

        mcp_client = await mcp_pool.get(current_tool.mcpId, self.task.metadata.userId)
        if not mcp_client:
            _logger.exception("[MCPAgentExecutor] MCP客户端不存在: %s", current_tool.mcpId)
            state.stepStatus = StepStatus.ERROR
            state.errorMessage = {
                "err_msg": f"MCP客户端不存在: {current_tool.mcpId}",
                "data": self._current_input,
            }
            self.task.state = state
            return

        try:
            output_data = await mcp_client.call_tool(current_tool.toolName, self._current_input)
        except anyio.ClosedResourceError as e:
            _logger.exception("[MCPAgentExecutor] MCP客户端连接已关闭: %s", current_tool.mcpId)
            # 停止当前用户MCP进程
            await mcp_pool.stop(current_tool.mcpId, self.task.metadata.userId)
            state.stepStatus = StepStatus.ERROR
            state.errorMessage = {
                "err_msg": str(e),
                "data": self._current_input,
            }
            self.task.state = state
            return
        except Exception as e:
            _logger.exception("[MCPAgentExecutor] 执行步骤 %s 时发生错误", state.stepName)
            state.stepStatus = StepStatus.ERROR
            state.errorMessage = {
                "err_msg": str(e),
                "data": self._current_input,
            }
            self.task.state = state
            return

        _logger.error("当前工具名称: %s, 输出参数: %s", state.stepName, output_data)
        if output_data.isError:
            err = ""
            for output in output_data.content:
                if isinstance(output, TextContent):
                    err += output.text
            state.stepStatus = StepStatus.ERROR
            state.errorMessage = {
                "err_msg": err,
                "data": {},
            }
            self.task.state = state
            return

        message = ""
        for output in output_data.content:
            if isinstance(output, TextContent):
                message += output.text
        output_data = {
            "message": message,
        }

        # 先更新状态为成功
        state.stepStatus = StepStatus.SUCCESS
        self.task.state = state

        await self._push_message(EventType.STEP_INPUT, self._current_input)
        await self._push_message(EventType.STEP_OUTPUT, output_data)
        self.task.context.append(
            self._create_executor_history(
                step_status=StepStatus.SUCCESS,
                input_data=self._current_input,
                output_data=output_data,
            ),
        )

    async def generate_params_with_null(self) -> None:
        """生成参数补充"""
        self._validate_task_state()
        self._validate_current_tool()
        state = cast("ExecutorCheckpoint", self.task.state)
        current_tool = cast("MCPTools", self._current_tool)

        params_with_null = await self._planner.get_missing_param(
            current_tool,
            self._current_input,
            state.errorMessage,
        )
        error_msg_str = self._get_error_message_str(state.errorMessage)
        error_message = await self._planner.change_err_message_to_description(
            error_message=error_msg_str,
            tool=current_tool,
            input_params=self._current_input,
        )

        # 先更新状态
        state.executorStatus = ExecutorStatus.WAITING
        state.stepStatus = StepStatus.PARAM
        self.task.state = state

        await self._push_message(
            EventType.STEP_WAITING_FOR_PARAM, data={"message": error_message, "params": params_with_null},
        )
        self.task.context.append(
            self._create_executor_history(
                step_status=state.stepStatus,
                extra_data={
                    "message": error_message,
                    "params": params_with_null,
                },
            ),
        )

    async def get_next_step(self) -> None:
        """获取下一步"""
        self._validate_task_state()
        state = cast("ExecutorCheckpoint", self.task.state)

        if self._step_cnt < AGENT_MAX_STEPS:
            self._step_cnt += 1
            history = await self._host.assemble_memory(self.task.runtime, self.task.context)
            max_retry = 3
            step = None
            for _ in range(max_retry):
                try:
                    step = await self._planner.create_next_step(history, self.tool_list)
                    if step.tool_id in self.tools:
                        break
                except Exception:
                    _logger.exception("[MCPAgentExecutor] 获取下一步失败，重试中...")
            if step is None or step.tool_id not in self.tools:
                step = Step(
                    tool_id=AGENT_FINAL_STEP_NAME,
                    description=AGENT_FINAL_STEP_NAME,
                )
            state.stepId = uuid.uuid4()
            state.stepName = step.tool_id
            state.stepStatus = StepStatus.INIT
        else:
            # 没有下一步了，结束流程
            state.stepName = AGENT_FINAL_STEP_NAME
        self.task.state = state

    async def error_handle_after_step(self) -> None:
        """步骤执行失败后的错误处理"""
        self._validate_task_state()
        state = cast("ExecutorCheckpoint", self.task.state)
        state.stepStatus = StepStatus.ERROR
        state.executorStatus = ExecutorStatus.ERROR
        self.task.state = state

        await self._push_message(EventType.STEP_END, data={})
        await self._push_message(EventType.EXECUTOR_STOP, data={})
        await self._add_error_to_context(state.stepStatus)

    async def work(self) -> None:  # noqa: C901, PLR0912
        """执行当前步骤"""
        self._validate_task_state()
        state = cast("ExecutorCheckpoint", self.task.state)

        if state.stepStatus == StepStatus.INIT:
            await self.get_tool_input_param(is_first=True)
            if not self._user.autoExecute:
                # 等待用户确认
                await self.confirm_before_step()
                return
            state.stepStatus = StepStatus.RUNNING
            self.task.state = state
        elif state.stepStatus in [StepStatus.PARAM, StepStatus.WAITING, StepStatus.RUNNING]:
            if state.stepStatus == StepStatus.PARAM:
                self._remove_last_context_if_same_step()
                await self.get_tool_input_param(is_first=False)
            elif state.stepStatus == StepStatus.WAITING:
                if self.params:
                    self._remove_last_context_if_same_step()
                else:
                    state.executorStatus = ExecutorStatus.CANCELLED
                    state.stepStatus = StepStatus.CANCELLED
                    self.task.state = state

                    await self._push_message(EventType.STEP_END, data={})
                    await self._push_message(EventType.EXECUTOR_STOP, data={})
                    self._update_last_context_status(StepStatus.CANCELLED)
                    return
            max_retry = 5
            for i in range(max_retry):
                if i != 0:
                    await self.get_tool_input_param(is_first=True)
                await self.run_step()
                if state.stepStatus == StepStatus.SUCCESS:
                    break
        elif state.stepStatus == StepStatus.ERROR:
            # 错误处理
            if self._retry_times >= AGENT_MAX_RETRY_TIMES:
                await self.error_handle_after_step()
            elif self._user.autoExecute:
                await self._handle_step_error_and_continue()
            else:
                mcp_tool = self.tools[state.stepName]
                error_msg = self._get_error_message_str(state.errorMessage)
                is_param_error = await self._planner.is_param_error(
                    await self._host.assemble_memory(self.task.runtime, self.task.context),
                    error_msg,
                    mcp_tool,
                    "",
                    self._current_input,
                )
                if is_param_error.is_param_error:
                    # 如果是参数错误，生成参数补充
                    await self.generate_params_with_null()
                else:
                    await self._handle_step_error_and_continue()
        elif state.stepStatus == StepStatus.SUCCESS:
            await self.get_next_step()

    async def summarize(self) -> None:
        """总结"""
        async for chunk in self._planner.generate_answer(
            await self._host.assemble_memory(self.task.runtime, self.task.context),
        ):
            await self._push_message(
                EventType.TEXT_ADD,
                data=chunk,
            )
            self.task.runtime.fullAnswer += chunk

    async def run(self) -> None:
        """执行MCP Agent的主逻辑"""
        self._validate_task_state()
        state = cast("ExecutorCheckpoint", self.task.state)

        # 初始化MCP服务
        await self.load_mcp()
        data = {}
        if state.executorStatus == ExecutorStatus.INIT:
            # 初始化状态
            state.executorId = str(uuid.uuid4())
            state.executorName = (await self._planner.get_flow_name()).flow_name
            flow_risk = await self._planner.get_flow_excute_risk(self.tool_list)
            if self._user.autoExecute:
                data = flow_risk.model_dump(exclude_none=True, by_alias=True)
            await self.get_next_step()
            self.task.state = state

        state.executorStatus = ExecutorStatus.RUNNING
        self.task.state = state

        if state.stepName == AGENT_FINAL_STEP_NAME:
            # 如果已经是最后一步，直接结束
            await self._handle_final_step()
            return

        try:
            while state.executorStatus == ExecutorStatus.RUNNING:
                await self.work()

            if state.stepName == AGENT_FINAL_STEP_NAME:
                # 如果已经是最后一步，直接结束
                await self._handle_final_step()
        except Exception as e:
            _logger.exception("[MCPAgentExecutor] 执行过程中发生错误")
            state.executorStatus = ExecutorStatus.ERROR
            state.errorMessage = {
                "err_msg": str(e),
                "data": {},
            }
            state.stepStatus = StepStatus.ERROR
            self.task.state = state

            await self._push_message(EventType.STEP_END, data={})
            await self._push_message(EventType.EXECUTOR_STOP, data={})
            await self._add_error_to_context(state.stepStatus)
        finally:
            for mcp_service in self._mcp_list:
                try:
                    await mcp_pool.stop(mcp_service.id, self.task.metadata.userId)
                except Exception:
                    _logger.exception("[MCPAgentExecutor] 停止MCP客户端时发生错误")
