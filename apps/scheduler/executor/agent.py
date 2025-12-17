# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Agent执行器"""

import logging
import uuid
from typing import Any

from mcp.types import TextContent
from pydantic import Field, ValidationError

from apps.constants import AGENT_FINAL_STEP_NAME, AGENT_MAX_RETRY_TIMES, AGENT_MAX_STEPS
from apps.models import ExecutorHistory, ExecutorStatus, MCPTools, StepStatus
from apps.models.task import ExecutorCheckpoint
from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.mcp_agent.host import MCPHost
from apps.scheduler.mcp_agent.plan import MCPPlanner
from apps.scheduler.pool.mcp.pool import mcp_pool
from apps.schemas.enum_var import EventType
from apps.schemas.flow import AgentAppMetadata
from apps.schemas.mcp import MCPRiskConfirm, Step
from apps.schemas.task import AgentCheckpointExtra, AgentHistoryExtra
from apps.services.appcenter import AppCenterManager
from apps.services.mcp_service import MCPServiceManager
from apps.services.user import UserManager

_logger = logging.getLogger(__name__)

class MCPAgentExecutor(BaseExecutor):
    """MCP Agent执行器"""

    agent_id: uuid.UUID = Field(default=uuid.uuid4(), description="App ID作为Agent ID")
    agent_description: str = Field(default="", description="Agent描述")
    params: dict[str, Any] | None = Field(
        default=None,
        description="流执行过程中的参数补充",
        alias="params",
    )

    async def init(self) -> None:
        """初始化MCP Agent"""
        # 若question为空，则使用task中的userInput
        if not self.question:
            self.question = self.task.runtime.userInput

        # 初始化必要变量
        self._step_cnt: int = 0
        self._retry_times: int = 0
        self._mcp_list: list = []
        self._current_input: dict = {}
        self._current_tool: MCPTools | None = None
        self._current_goal: str = ""
        self._tool_list: dict[str, MCPTools] = {}
        # 初始化MCP Host相关对象
        self._planner = MCPPlanner(self.task)
        self._host = MCPHost(self.task)
        user = await UserManager.get_user(self.task.metadata.userId)
        if not user:
            err = "[MCPAgentExecutor] 用户不存在: %s"
            _logger.error(err)
            raise RuntimeError(err)
        self._user = user
        # 获取历史
        await self._load_history()

        # 初始化任务状态（如果不存在）
        if not self.task.state:
            self.task.state = ExecutorCheckpoint(
                taskId=self.task.metadata.id,
                appId=self.agent_id,
                executorId="",
                executorName="",
                executorStatus=ExecutorStatus.INIT,
                stepId=uuid.uuid4(),
                stepName="",
                stepStatus=StepStatus.INIT,
                stepType="",
            )

        # 从state.extraData恢复状态（如果存在）
        self._restore_extra_data()

    def _restore_extra_data(self) -> None:
        """从 task.state.extraData 恢复所有状态"""
        if not self.task.state or not self.task.state.extraData:
            return

        try:
            checkpoint_extra = AgentCheckpointExtra.model_validate(self.task.state.extraData)
            self._current_input = checkpoint_extra.current_input
            self._retry_times = checkpoint_extra.retry_times
            self._current_goal = checkpoint_extra.step_goal
            self._step_cnt = checkpoint_extra.step_cnt
            _logger.info(
                "[MCPAgentExecutor] 从checkpoint恢复extraData - "
                "retry_times: %s, step_goal: %s, step_cnt: %s",
                self._retry_times,
                self._current_goal,
                self._step_cnt,
            )
        except (ValidationError, KeyError, TypeError) as e:
            _logger.warning("[MCPAgentExecutor] 从checkpoint恢复extraData失败: %s", e)

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
            mcp_service = await MCPServiceManager.get_mcp_service(mcp_id)
            if mcp_service:
                self._mcp_list.append(mcp_service)

                for tool in await MCPServiceManager.get_mcp_tools(mcp_id):
                    self._tool_list[tool.toolName] = tool

        self._tool_list[AGENT_FINAL_STEP_NAME] = MCPTools(
            mcpId="", toolName=AGENT_FINAL_STEP_NAME, description="结束流程的工具",
            inputSchema={}, outputSchema={},
        )

    async def get_tool_input_param(self, *, is_first: bool) -> None:
        """获取工具输入参数"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        # 获取输入参数
        self._current_tool = self._tool_list[self.task.state.stepName]

        # 对于首次调用,使用空的current_input
        current_input = {} if is_first else self._current_input

        self._current_input = await self._host.fill_params(
            self._current_tool,
            self.task,
            current_input,
            self.params,
            self._current_goal,
        )

    def _get_error_message_str(self, error_message: dict | str | None) -> str:
        """将错误消息转换为字符串"""
        if isinstance(error_message, dict):
            return str(error_message.get("err_msg", ""))
        return str(error_message) if error_message else ""

    def _update_last_context_status(self, step_status: StepStatus, output_data: dict | None = None) -> None:
        """更新最后一个context的状态(如果是当前步骤)"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)
        if len(self.task.context) and self.task.context[-1].stepId == self.task.state.stepId:
            self.task.context[-1].stepStatus = step_status
            if output_data is not None:
                self.task.context[-1].outputData = output_data

    def _set_step_error(self, error_msg: str, data: dict | None = None) -> None:
        """设置步骤状态为ERROR"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)
        self.task.state.stepStatus = StepStatus.ERROR
        self.task.state.errorMessage = {
            "err_msg": error_msg,
            "data": data if data is not None else self._current_input,
        }

    async def _add_error_to_context(self, step_status: StepStatus) -> None:
        """添加错误到context,先移除重复的步骤再添加"""
        self._remove_last_context_if_same_step()
        self.task.context.append(
            self._create_executor_history(step_status=step_status, step_goal=self._current_goal),
        )

    async def _handle_final_step(self) -> None:
        """处理最终步骤,设置状态并总结"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)
        self.task.state.executorStatus = ExecutorStatus.SUCCESS
        self.task.state.stepStatus = StepStatus.SUCCESS
        await self.summarize()

    def _create_executor_history(
        self,
        step_status: StepStatus,
        input_data: dict | None = None,
        output_data: dict | None = None,
        step_goal: str = "",
    ) -> ExecutorHistory:
        """创建ExecutorHistory对象"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        # 使用AgentHistoryExtra数据结构保存extra_data
        extra_data = AgentHistoryExtra(step_goal=step_goal).model_dump()

        return ExecutorHistory(
            taskId=self.task.metadata.id,
            stepId=self.task.state.stepId,
            stepName=self._current_tool.toolName if self._current_tool else self.task.state.stepName,
            stepType=str(self._current_tool.id) if self._current_tool else "",
            stepStatus=step_status,
            inputData=input_data or {},
            outputData=output_data or {},
            extraData=extra_data,
        )

    def _remove_last_context_if_same_step(self) -> None:
        """如果最后一个context是当前步骤，则删除它"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)
        if len(self.task.context) and self.task.context[-1].stepId == self.task.state.stepId:
            del self.task.context[-1]

    def _update_checkpoint_extra_data(self) -> None:
        """更新checkpoint的extraData"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        # 使用AgentCheckpointExtra数据结构保存checkpoint的extra_data
        checkpoint_extra = AgentCheckpointExtra(
            current_input=self._current_input,
            error_message=self._get_error_message_str(self.task.state.errorMessage),
            retry_times=self._retry_times,
            step_goal=self._current_goal,
            step_cnt=self._step_cnt,
        )
        self.task.state.extraData = checkpoint_extra.model_dump()
        _logger.info(
            "[MCPAgentExecutor] 更新checkpoint extraData - "
            "retry_times: %s, step_goal: %s, step_cnt: %s",
            self._retry_times,
            self._current_goal,
            self._step_cnt,
        )

    async def _handle_step_error_and_continue(self) -> None:
        """处理步骤错误并继续下一步"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)
        error_output = {"message": self.task.state.errorMessage}

        # 先更新stepStatus
        self.task.state.stepStatus = StepStatus.ERROR
        # 增加重试次数
        self._retry_times += 1

        await self._push_message(
            EventType.STEP_OUTPUT,
            data=error_output,
        )

        # 更新或添加错误到context
        if len(self.task.context) and self.task.context[-1].stepId == self.task.state.stepId:
            self._update_last_context_status(StepStatus.ERROR, error_output)
        else:
            self.task.context.append(
                self._create_executor_history(
                    step_status=StepStatus.ERROR,
                    input_data=self._current_input,
                    output_data=error_output,
                    step_goal=self._current_goal,
                ),
            )
        await self.get_next_step()

    async def confirm_before_step(self) -> None:
        """确认前步骤"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)
        if self._current_tool is None:
            err = "[MCPAgentExecutor] 当前工具不存在"
            _logger.error(err)
            raise RuntimeError(err)

        confirm_message = await self._planner.get_tool_risk(self._current_tool, self._current_input)

        # 先更新状态
        self.task.state.executorStatus = ExecutorStatus.WAITING
        self.task.state.stepStatus = StepStatus.WAITING

        await self._push_message(
            EventType.STEP_WAITING_FOR_START, confirm_message.model_dump(exclude_none=True, by_alias=True),
        )
        self.task.context.append(
            self._create_executor_history(
                step_status=self.task.state.stepStatus,
                step_goal=self._current_goal,
            ),
        )
        # 进入等待状态前保存checkpoint
        self._update_checkpoint_extra_data()

    async def run_step(self) -> None:
        """执行步骤"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)
        self.task.state.executorStatus = ExecutorStatus.RUNNING
        self.task.state.stepStatus = StepStatus.RUNNING
        if self._current_tool is None:
            err = "[MCPAgentExecutor] 当前工具不存在"
            _logger.error(err)
            raise RuntimeError(err)

        try:
            mcp_client = await mcp_pool.get(self._current_tool.mcpId, self.task.metadata.userId)
            output_data = await mcp_client.call_tool(self._current_tool.toolName, self._current_input)
        except Exception as e:
            _logger.exception("[MCPAgentExecutor] 执行步骤 %s 时发生错误", self.task.state.stepName)
            # 统一停止MCP进程，不再区分异常类型
            await mcp_pool.stop(self._current_tool.mcpId, self.task.metadata.userId)
            self._set_step_error(str(e))
            return

        _logger.info("[MCPAgentExecutor] 当前工具名称: %s, 输出参数: %s", self.task.state.stepName, output_data)
        if output_data.isError:
            err = ""
            for output in output_data.content:
                if isinstance(output, TextContent):
                    err += output.text
            self._set_step_error(err, {})
            return

        message = ""
        for output in output_data.content:
            if isinstance(output, TextContent):
                message += output.text
        output_data = {
            "message": message,
        }

        # 先更新状态为成功
        self.task.state.stepStatus = StepStatus.SUCCESS

        await self._push_message(EventType.STEP_INPUT, self._current_input)
        await self._push_message(EventType.STEP_OUTPUT, output_data)
        self.task.context.append(
            self._create_executor_history(
                step_status=StepStatus.SUCCESS,
                input_data=self._current_input,
                output_data=output_data,
                step_goal=self._current_goal,
            ),
        )

    async def generate_params_with_null(self) -> None:
        """生成参数补充"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)
        if self._current_tool is None:
            err = "[MCPAgentExecutor] 当前工具不存在"
            _logger.error(err)
            raise RuntimeError(err)

        params_with_null = await self._planner.get_missing_param(
            self._current_tool,
            self._current_input,
            self.task.state.errorMessage,
        )
        # TODO
        error_msg = self._get_error_message_str(self.task.state.errorMessage)

        # 先更新状态
        self.task.state.executorStatus = ExecutorStatus.WAITING
        self.task.state.stepStatus = StepStatus.PARAM

        await self._push_message(
            EventType.STEP_WAITING_FOR_PARAM, data={"message": error_msg, "params": params_with_null},
        )
        self.task.context.append(
            self._create_executor_history(
                step_status=self.task.state.stepStatus,
                step_goal=self._current_goal,
            ),
        )
        # 进入等待状态前保存checkpoint
        self._update_checkpoint_extra_data()

    async def get_next_step(self) -> None:
        """获取下一步"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        if self._step_cnt < AGENT_MAX_STEPS:
            self._step_cnt += 1
            max_retry = 3
            step = None
            for _ in range(max_retry):
                try:
                    step = await self._planner.create_next_step(list(self._tool_list.values()), self.task, self.llm)
                    if step.tool_name in self._tool_list:
                        break
                except Exception:
                    _logger.exception("[MCPAgentExecutor] 获取下一步失败，重试中...")
            if step is None or step.tool_name not in self._tool_list:
                step = Step(
                    tool_name=AGENT_FINAL_STEP_NAME,
                    description=AGENT_FINAL_STEP_NAME,
                )
            self.task.state.stepId = uuid.uuid4()
            self.task.state.stepName = step.tool_name
            self.task.state.stepStatus = StepStatus.INIT
            # 保存步骤目标
            self._current_goal = step.description
            # 重置重试次数
            self._retry_times = 0
            # 更新checkpoint的extraData
            self._update_checkpoint_extra_data()
        else:
            # 没有下一步了，结束流程
            self.task.state.stepName = AGENT_FINAL_STEP_NAME
            self._current_goal = AGENT_FINAL_STEP_NAME

    async def error_handle_after_step(self) -> None:
        """步骤执行失败后的错误处理"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)
        error_output = {"message": self.task.state.errorMessage}
        self.task.state.stepStatus = StepStatus.ERROR
        self.task.state.executorStatus = ExecutorStatus.ERROR

        await self._push_message(EventType.STEP_OUTPUT, data=error_output)
        await self._add_error_to_context(self.task.state.stepStatus)

    async def work(self) -> None:  # noqa: C901, PLR0912, PLR0915
        """执行当前步骤"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        # 处理初始化状态
        if self.task.state.stepStatus == StepStatus.INIT:
            await self.get_tool_input_param(is_first=True)
            if not self._user.autoExecute:
                # 等待用户确认
                await self.confirm_before_step()
                return
            self.task.state.stepStatus = StepStatus.RUNNING

        # 处理参数补充状态
        if self.task.state.stepStatus == StepStatus.PARAM:
            self._remove_last_context_if_same_step()
            await self.get_tool_input_param(is_first=False)

        # 处理等待状态
        if self.task.state.stepStatus == StepStatus.WAITING:
            should_cancel = False
            if self.params:
                # 解析风险确认参数
                try:
                    risk_confirm = MCPRiskConfirm.model_validate(self.params)
                    if risk_confirm.confirm:
                        # 用户确认继续执行
                        self._remove_last_context_if_same_step()
                        await self.get_tool_input_param(is_first=False)
                    else:
                        # 用户拒绝执行
                        should_cancel = True
                except ValidationError as e:
                    _logger.warning("[MCPAgentExecutor] 解析风险确认参数失败: %s, 取消执行", e)
                    should_cancel = True
            else:
                # 没有参数则取消执行
                should_cancel = True

            if should_cancel:
                self.task.state.executorStatus = ExecutorStatus.CANCELLED
                self.task.state.stepStatus = StepStatus.CANCELLED
                await self._push_message(EventType.STEP_OUTPUT, data={})
                self._update_last_context_status(StepStatus.CANCELLED)
                return

        # 执行步骤（PARAM、WAITING、RUNNING 状态都需要执行）
        if self.task.state.stepStatus in [StepStatus.PARAM, StepStatus.WAITING, StepStatus.RUNNING]:
            for i in range(AGENT_MAX_RETRY_TIMES):
                if i != 0:
                    await self.get_tool_input_param(is_first=True)
                await self.run_step()
                if self.task.state.stepStatus == StepStatus.SUCCESS:
                    break

        # 处理错误状态
        elif self.task.state.stepStatus == StepStatus.ERROR:
            if self._retry_times >= AGENT_MAX_RETRY_TIMES:
                await self.error_handle_after_step()
            elif self._user.autoExecute:
                await self._handle_step_error_and_continue()
            else:
                mcp_tool = self._tool_list[self.task.state.stepName]
                error_msg = self._get_error_message_str(self.task.state.errorMessage)
                is_param_error = await self._planner.is_param_error(
                    self.task,
                    error_msg,
                    mcp_tool,
                    self._current_goal,
                    self._current_input,
                )
                if is_param_error.is_param_error:
                    # 如果是参数错误，生成参数补充
                    await self.generate_params_with_null()
                else:
                    await self._handle_step_error_and_continue()

        # 处理成功状态
        elif self.task.state.stepStatus == StepStatus.SUCCESS:
            await self.get_next_step()

    async def summarize(self) -> None:
        """总结"""
        thinking_started = False
        async for chunk in self._planner.generate_answer(
            self.task,
            self.llm,
        ):
            if chunk.reasoning_content:
                if not thinking_started:
                    await self._push_message(
                        EventType.TEXT_ADD,
                        data="<think>",
                    )
                    self.task.runtime.fullAnswer += "<think>"
                    thinking_started = True

                await self._push_message(
                    EventType.TEXT_ADD,
                    data=chunk.reasoning_content,
                )
                self.task.runtime.fullAnswer += chunk.reasoning_content

            if chunk.content:
                if thinking_started:
                    await self._push_message(
                        EventType.TEXT_ADD,
                        data="</think>",
                    )
                    self.task.runtime.fullAnswer += "</think>"
                    thinking_started = False

                await self._push_message(
                    EventType.TEXT_ADD,
                    data=chunk.content,
                )
                self.task.runtime.fullAnswer += chunk.content

        if thinking_started:
            await self._push_message(
                EventType.TEXT_ADD,
                data="</think>",
            )
            self.task.runtime.fullAnswer += "</think>"

    async def run(self) -> None:
        """执行MCP Agent的主逻辑"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        # 初始化MCP服务
        await self.load_mcp()
        if self.task.state.executorStatus == ExecutorStatus.INIT:
            # 初始化状态
            self.task.state.executorId = str(uuid.uuid4())
            self.task.state.executorName = await self._planner.get_flow_name(self.llm)
            await self.get_next_step()

        self.task.state.executorStatus = ExecutorStatus.RUNNING

        try:
            if self.task.state.stepName == AGENT_FINAL_STEP_NAME:
                # 如果已经是最后一步，直接结束
                await self._handle_final_step()
            else:
                while self.task.state.executorStatus == ExecutorStatus.RUNNING:
                    await self.work()
                    if self.task.state.stepName == AGENT_FINAL_STEP_NAME:
                        # 如果已经是最后一步，直接结束
                        await self._handle_final_step()
                        break
        except Exception as e:
            _logger.exception("[MCPAgentExecutor] 执行过程中发生错误")
            self.task.state.executorStatus = ExecutorStatus.ERROR
            self.task.state.errorMessage = {
                "err_msg": str(e),
                "data": {},
            }
            self.task.state.stepStatus = StepStatus.ERROR
            error_output = {"message": self.task.state.errorMessage}

            await self._push_message(EventType.STEP_OUTPUT, data=error_output)
            await self._add_error_to_context(self.task.state.stepStatus)
        finally:
            # 更新checkpoint的extraData（统一在执行结束时更新）
            self._update_checkpoint_extra_data()
            # 清理MCP客户端
            for mcp_service in self._mcp_list:
                try:
                    await mcp_pool.stop(mcp_service.id, self.task.metadata.userId)
                except Exception:
                    _logger.exception("[MCPAgentExecutor] 停止MCP客户端时发生错误")
