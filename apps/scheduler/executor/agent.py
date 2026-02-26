# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Agent执行器"""

import json
import logging
import platform
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from mcp.types import TextContent
from pydantic import Field, ValidationError

from apps.common.config import config
from apps.constants import AGENT_MAX_STEPS
from apps.models import ExecutorHistory, ExecutorStatus, LanguageType, MCPTools, StepStatus
from apps.models.task import ExecutorCheckpoint
from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.mcp_agent.func import READ_TOOL_FUNCTION, UPDATE_TOOL_FUNCTION
from apps.scheduler.mcp_agent.host import MCPHost
from apps.scheduler.mcp_agent.plan import MCPPlanner
from apps.scheduler.pool.mcp.pool import mcp_pool
from apps.schemas.enum_var import EventType
from apps.schemas.llm import LLMToolCall
from apps.schemas.mcp import MCPRiskConfirm
from apps.schemas.task import AgentCheckpointExtra, AgentHistoryExtra, TaskData
from apps.services.user import UserManager

_logger = logging.getLogger(__name__)

# 忽略风险检查的工具列表（安全的系统工具）
IGNORE_RISK_TOOL = {"update_todo_list", "read_todo_list"}


class MCPAgentPrompt:
    """MCP Agent提示词处理器"""

    def __init__(self, task: TaskData, role: str = "main") -> None:
        """初始化MCP Agent提示词处理器"""
        self.task = task
        self.role = role
        self.language: LanguageType = task.runtime.language
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._prompt_base_dir = Path(config.deploy.data_dir) / "prompts" / "system"


    def load_prompt(self, prompt_id: str, prompt_type: str = "part") -> str:
        """加载提示词"""
        prompt_file = self._prompt_base_dir / prompt_type / f"{prompt_id}.{self.language.value}.txt"

        if not prompt_file.exists():
            err = f"[MCPAgentPrompt] 提示词文件不存在: {prompt_file}"
            _logger.error(err)
            raise FileNotFoundError(err)

        return prompt_file.read_text(encoding="utf-8")


    def _format_env(self) -> str:
        """格式化环境变量"""
        os_version = f"{platform.system()} {platform.release()}"
        os_arch = platform.machine()
        current_date = datetime.now(tz=UTC).astimezone().strftime("%Y-%m-%d")
        user_id = self.task.metadata.userId

        env_prompt_template = self.load_prompt("env")
        template = self._env.from_string(env_prompt_template)

        return template.render(
            os_version=os_version,
            os_arch=os_arch,
            current_date=current_date,
            user_id=user_id,
        )


    def format_tools(self, tools: dict[str, MCPTools]) -> str:
        """格式化工具列表"""
        tool_prompt_template = self.load_prompt("tool")
        # 注意这里需要保持工具相同的情况下顺序稳定
        sorted_tools = dict(sorted(tools.items(), key=lambda x: x[0]))
        template = self._env.from_string(tool_prompt_template)

        return template.render(tools=sorted_tools)


    def format(self, template: str, tools: dict[str, MCPTools]) -> str:
        """格式化提示词模板"""
        result = template

        # 使用正则表达式匹配所有 {xxx.yyy} 格式的占位符
        pattern = r"\{([^.}]+)\.([^}]+)\}"
        matches = re.findall(pattern, template)

        for prompt_type, prompt_id in matches:
            placeholder = f"{{{prompt_type}.{prompt_id}}}"

            # 特殊处理env和tool
            if prompt_id == "env":
                replacement = self._format_env()
            elif prompt_id == "tool":
                replacement = self.format_tools(tools)
            else:
                replacement = self.load_prompt(prompt_id, prompt_type=prompt_type)

            result = result.replace(placeholder, replacement)

        return dedent(result.strip())


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
        self._mcp_list: list = []
        self._tool_list: dict[str, MCPTools] = {}
        self._system_prompt = ""
        self._step_tool_call_id = ""
        self._current_step_count = 0
        self._current_todo_list = ""

        user = await UserManager.get_user(self.task.metadata.userId)
        if not user:
            err = "[MCPAgentExecutor] 用户不存在: %s"
            _logger.error(err)
            raise RuntimeError(err)

        self._user = user
        self._planner = MCPPlanner(self.task)
        self._host = MCPHost(self.task)
        self._prompt_mgmt = MCPAgentPrompt(self.task)

        # 如果是新Conversation，还没有state
        if not self.task.state:
            # 使用用户输入的前20个字作为executorName
            # TODO：如果有sub-Agent的话，这里可考虑用小模型生成一个更合适的executorName
            user_input = self.task.runtime.userInput or ""
            self.task.state = ExecutorCheckpoint(
                taskId=self.task.metadata.id,
                appId=self.agent_id,
                executorId=str(uuid.uuid4()),
                executorName=user_input[:20],
                executorStatus=ExecutorStatus.INIT,
                stepId=uuid.uuid4(),
                stepName="",
                stepStatus=StepStatus.INIT,
                stepType="",
            )
        else:
            await self._restore_checkpoint()


    async def _restore_checkpoint(self) -> None:
        """从checkpoint恢复步骤计数和todo列表到内存变量"""
        if not self.task.state or not self.task.state.extraData:
            return

        try:
            checkpoint_extra = AgentCheckpointExtra.model_validate(self.task.state.extraData)
            self._current_step_count = checkpoint_extra.step_count
            self._current_todo_list = checkpoint_extra.todo_list
            # 恢复token统计信息到llm对象
            self.llm.input_tokens = checkpoint_extra.input_token
            self.llm.output_tokens = checkpoint_extra.output_token
            _logger.info("[MCPAgentExecutor] 从checkpoint恢复数据")
        except Exception:
            _logger.exception("[MCPAgentExecutor] 恢复checkpoint失败")


    async def create_tool_list(self, query: str) -> dict[str, MCPTools]:
        """创建工具列表"""
        _logger.info("[MCPAgentExecutor] 创建工具列表")
        # TODO：这里目前只使用了Embedding
        # TODO：后续考虑方案一：Embedding + Reranker进行工具选择；方案二（推荐）：tool_search() function
        tool_list = await self._host.select_tools(query=query, mcp_list=self._mcp_list, top_n=20)

        # 添加用于创建/更新TODO列表的工具
        update_todo_func = UPDATE_TOOL_FUNCTION[self.task.runtime.language]
        tool_list[update_todo_func["name"]] = MCPTools(
            mcpId="",
            toolName=update_todo_func["name"],
            description=self._prompt_mgmt.load_prompt("update_todo_list", "func"),
            inputSchema=update_todo_func["parameters"],
            outputSchema=update_todo_func["output"],
        )

        # 添加用于读取当前TODO列表的工具
        read_todo_func = READ_TOOL_FUNCTION[self.task.runtime.language]
        tool_list[read_todo_func["name"]] = MCPTools(
            mcpId="",
            toolName=read_todo_func["name"],
            description=self._prompt_mgmt.load_prompt("read_todo_list", "func"),
            inputSchema=read_todo_func["parameters"],
            outputSchema=read_todo_func["output"],
        )
        return tool_list


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


    async def _finish_message(
        self,
        role: str,
        step_status: StepStatus,
        input_data: dict | None = None,
        output_data: dict | None = None,
    ) -> None:
        """保存消息到历史记录"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        # 根据角色处理不同的推送逻辑
        if role == "assistant":
            # 从 input_data 中提取 assistant 文本
            assistant_text = input_data.get("assistant", "") if input_data else ""
            if assistant_text:
                await self._push_message(EventType.TEXT_ADD, assistant_text)
        elif role == "tool":
            # 推送工具输出
            await self._push_message(EventType.STEP_OUTPUT, output_data or {})

        extra_data = AgentHistoryExtra(
            role=role,
            tool_call_id=self._step_tool_call_id if role == "tool" else None,
        ).model_dump()

        # 保存消息到历史记录
        self.task.context.append(
            ExecutorHistory(
                taskId=self.task.metadata.id,
                stepId=self.task.state.stepId,
                stepName=self.task.state.stepName,
                stepType="",
                stepStatus=step_status,
                inputData=input_data or {},
                outputData=output_data or {},
                extraData=extra_data,
            ),
        )


    async def handle_waiting_status(self) -> bool:
        """处理WAITING状态，判断用户是否批准执行"""
        async def _cancel_and_cleanup() -> None:
            """取消任务并清理状态的内部函数"""
            if not self.task.state:
                return
            self.task.state.executorStatus = ExecutorStatus.CANCELLED
            self.task.state.stepStatus = StepStatus.CANCELLED
            await self._push_message(EventType.STEP_OUTPUT, data={})
            self._update_last_context_status(StepStatus.CANCELLED)

        # 用户消息不合法
        if not self.params:
            _logger.warning("[MCPAgentExecutor] 无参数，取消任务")
            await _cancel_and_cleanup()
            return False

        # 用户消息结构错误
        try:
            risk_confirm = MCPRiskConfirm.model_validate(self.params)
        except ValidationError as e:
            _logger.warning("[MCPAgentExecutor] 解析风险确认参数失败: %s, 取消执行", e)
            await _cancel_and_cleanup()
            return False

        # 用户不批准执行
        if not risk_confirm.confirm:
            _logger.info("[MCPAgentExecutor] 用户拒绝执行，取消任务")
            await _cancel_and_cleanup()
            return False

        if self.task.state:
            self.task.state.stepStatus = StepStatus.RUNNING
            # 根据stepId找到对应的history并标记风险已确认，避免重复弹出风险确认
            # TODO：逻辑有点冗余；目前还有问题
            for history in self.task.context:
                if history.stepId == self.task.state.stepId:
                    if history.extraData:
                        history_extra = AgentHistoryExtra.model_validate(history.extraData)
                    else:
                        history_extra = AgentHistoryExtra()
                    history_extra.risk_confirmed = True
                    history.extraData = history_extra.model_dump()
                    _logger.info("[MCPAgentExecutor] 标记工具 %s 风险已确认", history.stepName)
                    break

        return True


    async def handle_update_todo_step(
        self,
        tool_arguments: dict[str, Any],
        tool_history: ExecutorHistory,
    ) -> None:
        """处理更新TODO列表步骤，直接接受大模型Function Call的参数并存储todo list"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)
        _logger.info("[MCPAgentExecutor] 准备更新todo list")

        # 推送工具输入
        self.task.state.stepStatus = StepStatus.RUNNING
        await self._push_message(EventType.STEP_INPUT, tool_arguments)

        # 从大模型Function Call参数中提取todo_list
        todo_list = tool_arguments.get("todo_list", "")
        if not todo_list:
            _logger.warning("[MCPAgentExecutor] todo_list参数为空")
        self._current_todo_list = todo_list

        self.task.state.stepStatus = StepStatus.SUCCESS
        output_data = {"status": "success"}
        tool_history.stepStatus = StepStatus.SUCCESS
        tool_history.outputData = output_data
        await self._push_message(EventType.STEP_OUTPUT, output_data)


    async def handle_read_todo_step(self, tool_history: ExecutorHistory) -> None:
        """处理读取TODO步骤,返回当前todo list"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)
        _logger.info("[MCPAgentExecutor] 读取todo list")

        # 推送工具输入
        self.task.state.stepStatus = StepStatus.RUNNING
        input_data = {}
        await self._push_message(EventType.STEP_INPUT, input_data)

        self.task.state.stepStatus = StepStatus.SUCCESS
        output_data = {"todo": self._current_todo_list}
        tool_history.stepStatus = StepStatus.SUCCESS
        tool_history.outputData = output_data
        await self._push_message(EventType.STEP_OUTPUT, output_data)


    async def _handle_special_tool(
        self,
        selected_tool: MCPTools,
        tool_arguments: dict[str, Any],
        tool_history: ExecutorHistory,
    ) -> bool:
        """处理特殊工具（TODO相关工具）"""
        if selected_tool.toolName == UPDATE_TOOL_FUNCTION[self.task.runtime.language]["name"]:
            await self.handle_update_todo_step(tool_arguments, tool_history)
            return True

        if selected_tool.toolName == READ_TOOL_FUNCTION[self.task.runtime.language]["name"]:
            await self.handle_read_todo_step(tool_history)
            return True

        return False


    async def _check_and_confirm_risk(
        self,
        selected_tool: MCPTools,
        tool_params: dict[str, Any],
    ) -> bool:
        """检查并确认工具执行风险；需要确认为True，可以执行为False"""
        # 如果用户设置了自动执行，跳过风险检查
        if self._user.autoExecute:
            return False

        # 检查最后一个 history 是否为同一个工具且已确认风险
        # TODO：目前还有问题
        if (self.task.context and
            self.task.context[-1].extraData and
            self.task.context[-1].stepName == selected_tool.toolName and
            AgentHistoryExtra.model_validate(self.task.context[-1].extraData).risk_confirmed is True):
            # 已确认风险
            _logger.info("[MCPAgentExecutor] 工具 %s 已确认风险，跳过风险检查", selected_tool.toolName)
            return False

        # 未确认风险，需要确认
        _logger.info("[MCPAgentExecutor] autoExecute=False，需要确认工具风险")
        confirm_message = await self._planner.get_tool_risk(selected_tool, tool_params)
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)
        self.task.state.executorStatus = ExecutorStatus.WAITING
        self.task.state.stepStatus = StepStatus.WAITING

        await self._push_message(
            EventType.STEP_WAITING_FOR_START,
            confirm_message.model_dump(exclude_none=True, by_alias=True),
        )
        return True


    async def _execute_single_tool(
        self,
        tool_call: LLMToolCall,
        selected_tool: MCPTools,
        tool_history: ExecutorHistory,
    ) -> None:
        """执行单个工具"""
        tool_params = tool_call.arguments
        _logger.info("[MCPAgentExecutor] 执行工具: %s, 参数: %s", selected_tool.toolName, tool_params)
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        # 处理特殊工具
        if await self._handle_special_tool(selected_tool, tool_params, tool_history):
            return

        # 使用选择的工具和参数调用MCP
        mcp_client = await mcp_pool.get(selected_tool.mcpId, self.task.metadata.userId)
        output_data = await mcp_client.call_tool(selected_tool.toolName, tool_params)

        # 检查工具执行是否出错
        if output_data.isError:
            err = ""
            for output in output_data.content:
                if isinstance(output, TextContent):
                    err += output.text
            _logger.error("[MCPAgentExecutor] 工具 %s 执行失败: %s", selected_tool.toolName, err)
            raise RuntimeError(err)

        # 提取工具输出
        message = ""
        for output in output_data.content:
            if isinstance(output, TextContent):
                message += output.text

        # 将字符串化的JSON数组进行解码
        try:
            decoded_message = json.loads(message)
        except json.JSONDecodeError:
            _logger.warning("[MCPAgentExecutor] 工具输出不是有效的JSON，使用原始字符串")
            decoded_message = {"message": message}

        _logger.info("[MCPAgentExecutor] 工具 %s 执行成功", selected_tool.toolName)

        # 更新对应tool history的outputData
        tool_history.stepStatus = StepStatus.SUCCESS
        tool_history.outputData = decoded_message
        await self._push_message(EventType.STEP_OUTPUT, decoded_message)


    def _assemble_user_prompt(self) -> str:
        """组装用户提示词"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        user_template = self.task.runtime.userInput or ""

        # 判断当前步骤数是否超过最大步骤数
        if self._current_step_count >= AGENT_MAX_STEPS:
            _logger.warning("[MCPAgentExecutor] 当前步骤数 %d 已达到最大步骤数 %d",
                          self._current_step_count, AGENT_MAX_STEPS)
            user_template += r"""
                {alert.max_step_reached}
            """

        # 判断当前todo_list是否为空
        if not self._current_todo_list or self._current_todo_list.strip() == "":
            _logger.warning("[MCPAgentExecutor] 当前todo_list为空，添加todo_empty提示")
            user_template += r"""
                {alert.todo_empty}
            """

        return self._prompt_mgmt.format(template=user_template, tools=self._tool_list)


    async def _add_initial_user_message_if_needed(self) -> None:
        """判断是否需要添加初始 user 消息，如果需要则添加"""
        # 如果 history 为空，或者最后一个 assistant 消息后面没有跟随 tool 消息，则添加 user 消息
        need_user_message = False
        if not self.task.context:
            need_user_message = True
        else:
            last_history = self.task.context[-1]
            if last_history.extraData:
                history_extra = AgentHistoryExtra.model_validate(last_history.extraData)
                # 如果最后一个记录是 assistant 且后面没有 tool 消息，需要添加 user 消息
                if history_extra.role == "assistant":
                    need_user_message = True

        # 如果需要添加 user 消息，则添加；此时算作“第1步”
        if need_user_message:
            _logger.info("[MCPAgentExecutor] 添加初始 user 消息")
            self.task.runtime.userInput = self.question
            self._current_step_count = 1
            user_prompt = self._assemble_user_prompt()
            await self._finish_message(
                role="user",
                step_status=StepStatus.SUCCESS,
                input_data={"user": user_prompt},
            )


    async def _call_llm_and_create_pending_histories(self) -> list[ExecutorHistory]:
        """调用 LLM 并创建待执行的 history 列表"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        # 增加步骤计数
        self._current_step_count += 1
        _logger.info("[MCPAgentExecutor] 更新步骤计数: %d", self._current_step_count)

        # 调用模型
        system_prompt = self._system_prompt
        step_text_output, tool_calls = await self._host.call_llm_and_parse_tools(
            task=self.task,
            llm=self.llm,
            tool_list=self._tool_list,
            system_prompt=system_prompt,
        )

        # 立即保存 assistant history
        await self._finish_message(
            role="assistant",
            step_status=StepStatus.SUCCESS,
            input_data={"assistant": step_text_output},
        )

        # 没有工具调用，认为任务完成
        if not tool_calls:
            _logger.warning("[MCPAgentExecutor] LLM未返回工具调用")
            self.task.state.executorStatus = ExecutorStatus.SUCCESS
            return []

        # 创建状态为WAITING的tool history
        pending_histories: list[ExecutorHistory] = []
        for tool_call in tool_calls:
            # 提前判断工具是否存在，确定状态和输出数据
            if tool_call.name not in self._tool_list:
                _logger.error("[MCPAgentExecutor] 工具 %s 不存在于工具列表中，状态设为ERROR", tool_call.name)
                step_status = StepStatus.ERROR
                output_data = {"error": f"工具 {tool_call.name} 不存在于工具列表中"}
                should_add_to_pending = False
            else:
                step_status = StepStatus.WAITING
                output_data = {}
                should_add_to_pending = True

            extra_data = AgentHistoryExtra(
                role="tool",
                tool_call_id=tool_call.id,
            ).model_dump()
            history = ExecutorHistory(
                taskId=self.task.metadata.id,
                stepId=uuid.uuid4(),
                stepName=tool_call.name,
                stepType="",
                stepStatus=step_status,
                inputData=tool_call.arguments,
                outputData=output_data,
                extraData=extra_data,
            )
            self.task.context.append(history)
            if should_add_to_pending:
                pending_histories.append(history)

        return pending_histories


    def _find_pending_histories_from_context(self) -> list[ExecutorHistory]:
        """从 context 中查找所有连续的 WAITING 状态的 history"""
        _logger.info("[MCPAgentExecutor] resume=True，从history中查找WAITING状态的记录")
        pending_histories: list[ExecutorHistory] = []
        for history in reversed(self.task.context):
            if history.stepStatus == StepStatus.WAITING:
                # 从前面插入，保持原有顺序
                pending_histories.insert(0, history)
            else:
                # 遇到第一个非WAITING状态就停止
                break
        return pending_histories


    async def _execute_pending_histories(self, pending_histories: list[ExecutorHistory]) -> None:
        """统一执行所有待执行的 history"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        _logger.info("[MCPAgentExecutor] 开始执行 %d 个待执行的工具", len(pending_histories))
        for history in pending_histories:
            tool_name = history.stepName
            tool_arguments = history.inputData

            selected_tool = self._tool_list.get(tool_name)
            if not selected_tool:
                _logger.error("[MCPAgentExecutor] 工具 %s 不存在于工具列表中，状态改为ERROR", tool_name)
                history.stepStatus = StepStatus.ERROR
                history.outputData = {"error": f"工具 {tool_name} 不存在于工具列表中"}
                continue

            tool_call_id = ""
            if history.extraData:
                history_extra = AgentHistoryExtra.model_validate(history.extraData)
                tool_call_id = history_extra.tool_call_id or ""

            self.task.state.stepId = history.stepId
            self.task.state.stepName = selected_tool.toolName
            self.task.state.stepStatus = StepStatus.INIT
            self._step_tool_call_id = tool_call_id

            # 风险检查（非特殊工具才需要）
            if (
                selected_tool.toolName not in IGNORE_RISK_TOOL
                and await self._check_and_confirm_risk(selected_tool, tool_arguments)
            ):
                _logger.info("[MCPAgentExecutor] 工具 %s 需要风险确认，暂停执行", tool_name)
                # 等待用户确认
                break


            tool_call = LLMToolCall(
                id=tool_call_id,
                name=tool_name,
                arguments=tool_arguments,
            )
            try:
                await self._execute_single_tool(tool_call, selected_tool, history)
            except Exception as e:
                _logger.exception("[MCPAgentExecutor] 执行工具 %s 时发生错误", tool_name)
                # 停止MCP进程
                await mcp_pool.stop(selected_tool.mcpId, self.task.metadata.userId)
                # 设置错误状态
                self.task.state.stepStatus = StepStatus.ERROR
                self.task.state.errorMessage = {
                    "err_msg": str(e),
                    "data": tool_arguments,
                }
                history.stepStatus = StepStatus.ERROR
                history.outputData = {"error": str(e)}
                # 继续执行，不中断整个流程
                continue


    async def run_step(self, *, resume: bool = False) -> None:
        """执行步骤"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)
        self.task.state.executorStatus = ExecutorStatus.RUNNING

        # 获取待执行的 history 列表
        if not resume:
            pending_histories = await self._call_llm_and_create_pending_histories()
        else:
            pending_histories = self._find_pending_histories_from_context()

        await self._execute_pending_histories(pending_histories)


    # TODO：当前还未接入和测试
    async def generate_params_with_null(self) -> None:
        """生成参数补充"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        # 从最后一个history中获取工具名称和工具输入
        if not self.task.context:
            err = "[MCPAgentExecutor] 任务上下文为空，无法获取工具信息"
            _logger.error(err)
            raise RuntimeError(err)

        last_history = self.task.context[-1]
        tool_name = last_history.stepName

        # 从tool_list中获取对应的MCPTools
        current_tool = self._tool_list.get(tool_name)
        if not current_tool:
            err = f"[MCPAgentExecutor] 在tool_list中未找到工具: {tool_name}"
            _logger.error(err)
            raise RuntimeError(err)

        params_with_null = await self._planner.get_missing_param(
            current_tool,
            self.task.context[-1].inputData,
            self.task.state.errorMessage,
        )
        error_msg = self.task.state.errorMessage["err_msg"]

        self.task.state.executorStatus = ExecutorStatus.WAITING
        self.task.state.stepStatus = StepStatus.PARAM
        await self._push_message(
            EventType.STEP_WAITING_FOR_PARAM,
            {"message": error_msg, "params": params_with_null},
        )

    # TODO：当前还未接入和测试
    # TODO：考虑改为ask_user() function，让用户用自然语言澄清信息
    async def handle_param_status(self, history: ExecutorHistory) -> bool:
        """处理PARAM状态的逻辑"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        # 判断self.params是否为空
        if not self.params:
            _logger.warning("[MCPAgentExecutor] 用户没有输入参数，取消任务")
            self.task.state.executorStatus = ExecutorStatus.CANCELLED
            self.task.state.stepStatus = StepStatus.CANCELLED
            await self._push_message(EventType.STEP_OUTPUT, data={})
            self._update_last_context_status(StepStatus.CANCELLED)
            return False

        # 合并用户通过params传递的参数与history中的inputData
        if self.params:
            history.inputData.update(self.params)

        # 参数整合完成后，将状态改为Running
        self.task.state.stepStatus = StepStatus.WAITING
        self.task.state.executorStatus = ExecutorStatus.RUNNING
        _logger.info("[MCPAgentExecutor] PARAM状态，参数已整合，状态改为WAITING")
        return True


    def _save_checkpoint(self) -> None:
        """保存步骤计数和todo列表到checkpoint"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        checkpoint_extra = AgentCheckpointExtra(
            step_count=self._current_step_count,
            todo_list=self._current_todo_list,
            input_token=self.llm.input_tokens,
            output_token=self.llm.output_tokens,
        )
        self.task.state.extraData = checkpoint_extra.model_dump()
        _logger.debug(
            "[MCPAgentExecutor] 保存checkpoint: step_count=%d, todo_list=%s, input_token=%d, output_token=%d",
            self._current_step_count,
            self._current_todo_list[:50] if self._current_todo_list else "",
            self.llm.input_tokens,
            self.llm.output_tokens,
        )


    async def run(self) -> None:
        """执行MCP Agent的主逻辑"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        # 选择工具
        _logger.info("[MCPAgentExecutor] 创建工具列表并选择工具")
        self._tool_list = await self.create_tool_list(query=self.task.runtime.userInput)

        _logger.info("[MCPAgentExecutor] 创建系统提示词")
        system_template = r"""
{role.main}

{part.todo}
{part.final}
{part.tool}
{part.env}
        """
        self._system_prompt = self._prompt_mgmt.format(template=system_template, tools=self._tool_list)
        # 添加 user 消息
        await self._add_initial_user_message_if_needed()

        # 设置ExecutorStatus为RUNNING，开始循环
        self.task.state.executorStatus = ExecutorStatus.RUNNING
        while self.task.state.executorStatus == ExecutorStatus.RUNNING:
            # 取出最后一个history
            if len(self.task.context) > 0:
                last_history = self.task.context[-1]
                last_step_status = last_history.stepStatus

                # 1. 如果StepStatus为PARAM，进入填参逻辑
                if last_step_status == StepStatus.PARAM:
                    _logger.info("[MCPAgentExecutor] 检测到PARAM状态，处理参数确认")
                    if not await self.handle_param_status(last_history):
                        break

                # 2. 如果StepStatus为WAITING，进入确认逻辑
                if last_step_status == StepStatus.WAITING:
                    _logger.info("[MCPAgentExecutor] 检测到WAITING状态，等待用户批准")
                    if not await self.handle_waiting_status():
                        break
                    # 用户批准后，恢复执行
                    _logger.info("[MCPAgentExecutor] 用户批准执行，恢复执行待审批的工具")
                    await self.run_step(resume=True)
                    continue

            # 正常继续运行
            _logger.info("[MCPAgentExecutor] 运行Agent的一个Step")
            await self.run_step()

        # 运行结束清理MCP客户端
        for mcp_service in self._mcp_list:
            try:
                await mcp_pool.stop(mcp_service.id, self.task.metadata.userId)
            except Exception:
                _logger.exception("[MCPAgentExecutor] 停止MCP客户端时发生错误")
        self._save_checkpoint()
