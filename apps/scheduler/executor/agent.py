# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Agent执行器"""
import asyncio
import json
import logging
import platform
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent
from typing import Any
from collections.abc import AsyncGenerator
from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from mcp.types import TextContent
from pydantic import Field, ValidationError

from apps.common.config import config
from apps.constants import AGENT_MAX_STEPS
from apps.llm import LLM
from apps.models import ExecutorHistory, ExecutorStatus, LanguageType, MCPTools, StepStatus
from apps.models.task import ExecutorCheckpoint
from apps.scheduler.call.abstract.abstract import AbstractGenerator
from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.mcp_agent.func import READ_TOOL_FUNCTION, UPDATE_TOOL_FUNCTION, STREAM_OUTPUT_FUNCTION, \
    SELF_INTRODUCE_FUNCTION
from apps.scheduler.mcp_agent.host import MCPHost
from apps.scheduler.mcp_agent.plan import MCPPlanner
from apps.scheduler.pool.mcp.pool import mcp_pool
from apps.schemas.enum_var import EventType
from apps.schemas.flow import AgentAppMetadata, FlowAppMetadata
from apps.schemas.llm import LLMToolCall
from apps.schemas.mcp import MCPRiskConfirm
from apps.schemas.task import AgentCheckpointExtra, AgentHistoryExtra, TaskData
from apps.services.abstract_manager import AbstractManager
from apps.services.mcp_service import MCPServiceManager
from apps.services.record import RecordManager
from apps.services.user import UserManager

_logger = logging.getLogger(__name__)

# 忽略风险检查的工具列表（安全的系统工具）
IGNORE_RISK_TOOL = {"update_todo_list", "read_todo_list", "stream_output", "self_introduce"}


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
        self._prompt_call_dir = Path(config.deploy.data_dir) / "prompts" / "call"

    def load_prompt(self, prompt_id: str, prompt_type: str = "part") -> str:
        """加载提示词"""
        if prompt_type == "call":
            prompt_file = self._prompt_call_dir / f"{prompt_id}.{self.language.value}.txt"
        else:
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

    def _format_agent(self, agent_metadata: AgentAppMetadata) -> str:
        """格式化Agent信息（严格对齐_format_env的设计模式）"""
        # 加载agent模块的提示词模板（需新建agent.txt提示词文件）
        agent_prompt_template = self.load_prompt(prompt_type="role", prompt_id="main")
        template = self._env.from_string(agent_prompt_template)

        # 兜底默认值（和现有逻辑保持一致）
        agent_name = agent_metadata.name or "witty"
        agent_desc = agent_metadata.description or "是一款交互式CLI软件，能够帮助用户完成执行命令、修改知识库、分析系统运行状态、修改系统配置等操作系统相关的任务"  # noqa: E501

        return template.render(
            agent_name=agent_name,
            agent_desc=agent_desc,
        )

    def format(
            self,
            agent_metadata: FlowAppMetadata | AgentAppMetadata | None = None,
            template: str = "",
            tools: dict[str, MCPTools] | None = None,
    ) -> str:
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
            elif prompt_id == "tool" and tools:
                replacement = self.format_tools(tools)
            elif prompt_type == "role" and agent_metadata and isinstance(agent_metadata, AgentAppMetadata):
                replacement = self._format_agent(agent_metadata)
            else:
                replacement = self.load_prompt(prompt_id, prompt_type=prompt_type)

            result = result.replace(placeholder, replacement)

        return dedent(result.strip())

    def _build_stream_summary_prompt(
            self,
            current_tool_name: str,
            current_step: str,
            current_status: str,
            current_result: str,
            finish: bool,  # noqa: FBT001
    ) -> str:
        summary_template = self.load_prompt("stream_summary", prompt_type="call")
        template = self._env.from_string(summary_template)
        return template.render(
            current_tool=current_tool_name,
            current_step=current_step,
            current_status=current_status,
            current_result=current_result,
            finish=finish,
        )


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
        self._tool_calls = []
        self._mcp_list: list = []
        self._tool_list: dict[str, MCPTools] = {}
        self._system_prompt = ""
        self._step_tool_call_id = ""
        self._current_step_count = 0
        self._current_todo_list = ""
        self._current_intro_content = ""

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
        tool_list = await self._host.get_tools(mcp_list=self._mcp_list, user_id=self.task.metadata.userId)

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

        # ========== 流式输出工具 ==========
        stream_output_func = STREAM_OUTPUT_FUNCTION[self.task.runtime.language]
        tool_list[stream_output_func["name"]] = MCPTools(
            mcpId="",
            toolName=stream_output_func["name"],
            description=self._prompt_mgmt.load_prompt("stream_output", "func"),
            inputSchema=stream_output_func["parameters"],
            outputSchema=stream_output_func["output"],
        )
        # ========== 自我介绍工具 ==========
        self_introduce_func = SELF_INTRODUCE_FUNCTION[self.task.runtime.language]
        tool_list[self_introduce_func["name"]] = MCPTools(
            mcpId="",
            toolName=self_introduce_func["name"],
            description=self._prompt_mgmt.load_prompt("self_introduce", "func"),
            inputSchema=self_introduce_func["parameters"],
            outputSchema=self_introduce_func["output"],
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

        if role == "tool":
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

    async def handle_introduce_self_step(
            self,
            tool_arguments: dict[str, Any],
            tool_history: ExecutorHistory,
    ) -> None:
        """处理Agent自我介绍步骤：仅完成工具调用流程闭环，输出内容由大模型Function Call参数提供"""
        # 1. 校验任务状态
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在，无法执行自我介绍"
            _logger.error(err)
            raise RuntimeError(err)
        _logger.info("[MCPAgentExecutor] 开始执行Agent自我介绍步骤")

        # 2. 标记运行中 + 推送STEP_INPUT
        self.task.state.stepStatus = StepStatus.RUNNING
        await self._push_message(EventType.STEP_INPUT, tool_arguments)
        self._current_intro_content = tool_arguments.get("content", "").strip()
        # 3. 仅标记成功，无硬编码内容
        self.task.state.stepStatus = StepStatus.SUCCESS
        # 输出仅返回状态
        output_data = {"status": "success"}

        # 4. 更新工具历史
        tool_history.stepStatus = StepStatus.SUCCESS
        tool_history.outputData = output_data

        # 5. 推送STEP_OUTPUT，完成闭环
        await self._push_message(EventType.STEP_OUTPUT, output_data)
        _logger.info("[MCPAgentExecutor] Agent自我介绍步骤执行完成")

    async def handle_stream_output_step(
            self,
            tool_arguments: dict[str, Any],
            tool_history: ExecutorHistory,
    ) -> None:
        """实现流式输出"""
        # 基础校验
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        _logger.info("[MCPAgentExecutor] 执行流式输出工具，接收原始参数：%s", tool_arguments.get("content"))

        # 2. 提取到最近一次用户输入为止的完整上下文
        history_context, new_context = self._get_recent_context_summary(max_rounds=10)

        # 3. 组装完整的prompt（历史上下文 + 最新上下文）
        full_thinking = f"""
        请你作为Agent的交互表达助手，基于以下信息，生成适合人类阅读的自然语言内容：
        【当前阶段】
        {tool_arguments.get("content")}

        【历史执行结果】
        {history_context}

        【本轮新增执行结果】
        {new_context or "无新增操作"}

        """.strip()
        summary_prompt = full_thinking  # 最终传给LLM的prompt

        # 推送工具输入状态
        self.task.state.stepStatus = StepStatus.RUNNING
        await self._push_message(EventType.STEP_INPUT, tool_arguments)

        # 固定延迟
        delay = 0.5
        full_think_content = ""

        # ========== 核心：流式调用LLM并输出 ==========
        async for chunk in self._call_llm_for_summary_stream(summary_prompt):
            # 只过滤纯空的chunk，保留所有格式符号（\n/**/```等）
            if chunk and not chunk.isspace():
                # 累加完整内容（用于后续保存）
                full_think_content += chunk
                # 直接推送原生chunk，不做任何拆分！
                await self._push_message(EventType.TEXT_ADD, chunk)
                # 动态延迟：根据chunk长度调整（长内容快一点，短内容慢一点）
                chunk_length = len(chunk.strip())
                sleep_time = delay if chunk_length > 10 else delay * 2  # noqa: PLR2004
                await asyncio.sleep(sleep_time)

        # ========== 状态更新==========
        self.task.state.stepStatus = StepStatus.SUCCESS
        output_data = {
            "status": "success",
            "content": "完成流式输出",
        }
        tool_history.stepStatus = StepStatus.SUCCESS
        tool_history.outputData = output_data
        await self._push_message(EventType.STEP_OUTPUT, output_data)

        _logger.info(f"[MCPAgentExecutor] 流式推送完成，内容：{full_think_content[:100]}...")  # noqa: G004

    async def _call_llm_for_summary_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        直接调用你已有的 OpenAIProvider 流式 chat 方法
        逐chunk返回LLM生成的思考内容
        """  # noqa: D205
        try:
            # 构建标准聊天消息
            system_prompt = self._prompt_mgmt.load_prompt("stream_summary", prompt_type="call")
            messages = [
                {"role": "system", "content": system_prompt},  # 你的专业提示词
                {"role": "user", "content": prompt},  # 结构化参数（current_tool/step等）
            ]

            # streaming=True 会透传给 OpenAIProvider.chat，触发流式逻辑
            async for llm_chunk in self.llm.call(
                    messages=messages,
                    streaming=True,
                    include_thinking=False,
                    tools=None,
                    temperature=0.2,
            ):
                # 过滤空内容，只推送有效文本
                if llm_chunk.content and llm_chunk.content.strip():
                    yield llm_chunk.content

        except Exception as e:
            _logger.exception("[MCPAgentExecutor] 流式调用LLM失败: %s", str(e))
            # 兜底返回默认提示语
            yield "正在处理中，请稍等～"

    def _get_recent_context_summary(self, max_rounds: int = 10) -> tuple[str, str]:  # noqa: C901, PLR0912, PLR0915
        """
        从 task.context 中提取上下文并直接拆分「历史上下文」和「本轮新增上下文」
        :param max_rounds: 最多取最近几轮的历史（默认10轮，防止上下文过长）
        :return: (历史上下文文本, 本轮新增上下文文本)
        """  # noqa: D205
        if not self.task.context:
            return "当前任务上下文为空～", ""

        # ===================== 第一步：预处理当前Step的stepId（用于匹配新增内容） =====================
        current_step_id_strs = set()
        # 读取当前Step记录的stepId（在_call_llm_and_create_pending_histories中初始化的）
        if hasattr(self, "_current_step_id") and isinstance(self._current_step_id, set) and self._current_step_id:
            for step_id in self._current_step_id:
                # 兼容UUID对象/字符串格式
                if isinstance(step_id, uuid.UUID):
                    current_step_id_strs.add(str(step_id))
                elif isinstance(step_id, str) and step_id.strip():
                    current_step_id_strs.add(step_id.strip())

        # ===================== 第二步：提取核心上下文=====================
        user_input_index = -1

        recent_histories = self.task.context[-max_rounds:]
        # 找最近一次用户输入的位置
        for idx, history in enumerate(recent_histories):
            extra_data = history.extraData or {}
            role = extra_data.get("role", "")
            if role == "user":
                user_input_index = idx
                break

        # 截取从最近一次用户输入到最后的上下文
        target_histories = recent_histories[user_input_index:] if user_input_index != -1 else recent_histories

        # ===================== 第三步：拆分历史/新增上下文 =====================
        history_blocks = []  # 历史内容块
        new_blocks = []  # 本轮新增内容块

        for history in target_histories:
            # 1. 提取基础信息
            extra_data = history.extraData or {}
            role = extra_data.get("role", "unknown")
            step_name = history.stepName or "未命名步骤"
            step_status = history.stepStatus.value if hasattr(history.stepStatus, "value") else history.stepStatus
            input_data = history.inputData or {}
            output_data = history.outputData or {}

            # 2. 空值/长内容处理
            if role == "assistant" and "assistant" in input_data:
                assistant_content = input_data["assistant"] or ""
                input_data = {"思考内容": assistant_content}
            elif role == "tool" and step_name == "file_tool" and "content" in input_data:
                content = input_data.get("content", "")
                input_data = {"代码内容": content}
            elif role == "tool" and step_name == "self_introduce" and "content" in input_data:
                intro_content = input_data.get("content", "")
                input_data = {"自我介绍内容": intro_content}
            elif role == "user" and "user" in input_data:
                user_content = input_data.get("user", "")
                input_data = {"用户输入": user_content}

            # 3. 格式化当前块
            block_lines = [f"【{role} - {step_name} ({step_status})】"]
            if input_data:
                if step_name in ["self_introduce", "file_tool"] and len(input_data) == 1:
                    input_value = next(iter(input_data.values()))
                    block_lines.append(f"输入：{input_value}")
                else:
                    block_lines.append(f"输入：{json.dumps(input_data, ensure_ascii=False, indent=2)}")
            if output_data:
                block_lines.append(f"输出：{json.dumps(output_data, ensure_ascii=False, indent=2)}")
            block_lines.append("---")
            block_text = "\n".join(block_lines)

            # 4. 核心判断：当前块是否属于本轮新增（匹配stepId）
            step_id_str = str(history.stepId) if hasattr(history, "stepId") else ""
            is_current_step = step_id_str in current_step_id_strs if current_step_id_strs else False

            # 5. 分类到历史/新增
            if is_current_step:
                new_blocks.append(block_text)
            else:
                history_blocks.append(block_text)

        # ===================== 第四步：拼接最终结果 =====================
        # 历史上下文（无内容时返回兜底提示）
        history_context = "\n".join(history_blocks) if history_blocks else "当前任务上下文为空～"
        # 本轮新增上下文（无新增时返回空字符串）
        new_context = "\n".join(new_blocks) if new_blocks else ""

        return history_context, new_context

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

        if selected_tool.toolName == STREAM_OUTPUT_FUNCTION[self.task.runtime.language]["name"]:
            await self.handle_stream_output_step(tool_arguments, tool_history)
            return True

        if selected_tool.toolName == SELF_INTRODUCE_FUNCTION[self.task.runtime.language]["name"]:
            await self.handle_introduce_self_step(tool_arguments, tool_history)
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
        output_data = await MCPServiceManager.call_tool(
            mcp_id=selected_tool.mcpId,
            user_id=self.task.metadata.userId,
            tool_name=selected_tool.toolName,
            parameter=tool_params,
        )

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

        # 添加流式输出引导
        stream_guide = """
        你必须严格按以下规则调用stream_output工具：
        1. 自我介绍场景：调用self_introduce后立即调用stream_output，content=<自我介绍>，输出内容1:1原样、仅一次；
        2. 任务执行场景：按<任务规划>→<执行过程-初始化>→<执行过程-内容生成>→<执行过程-结果反馈>→<验证反馈>→<完成结果>顺序调用；
        3. 每个阶段的stream_output仅输出当前阶段内容，禁止跳步/重复；
        4. 仅<完成结果>阶段可总结全流程，其余阶段仅输出当前步骤信息；
        5. 禁止在无实质内容时调用stream_output。
        """
        user_template = stream_guide + (self.task.runtime.userInput or "")

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
            _logger.info("[MCPAgentExecutor] 添加初始 user 消息: %s", self.question)
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
        last_tool_calls = self._tool_calls or []
        step_text_output, tool_calls = await self._host.call_llm_and_parse_tools(
            task=self.task,
            llm=self.llm,
            tool_list=self._tool_list,
            system_prompt=system_prompt,
        )
        self._tool_calls = tool_calls or []
        _logger.info("[MCPAgentExecutor] LLM调用完成 工具调用: %s", tool_calls)
        # 立即保存 assistant history
        await self._finish_message(
            role="assistant",
            step_status=StepStatus.SUCCESS,
            input_data={"assistant": step_text_output},
        )

        # 没有工具调用，认为任务完成
        if not tool_calls:
            # 兜底使用流式输出总结：上一次tool最后一个tool是不是流式工具，但任务结束
            if last_tool_calls and last_tool_calls[-1].name != "stream_output":
                stream_tool_arguments = {
                    "content": step_text_output,
                    "is_final_summary": True,
                    "scene_type": "end",
                }
                step_id = uuid.uuid4()
                self._current_step_id.add(step_id)
                _logger.info("[MCPAgentExecutor] stream_output总结生成准备: %s", step_id)
                # 模拟tool_history
                final_tool_history = ExecutorHistory(
                    taskId=self.task.metadata.id,
                    stepId=step_id,
                    stepName="stream_output",
                    stepType="",
                    stepStatus=StepStatus.WAITING,
                    inputData=stream_tool_arguments,
                    outputData={},
                    extraData=AgentHistoryExtra(
                        role="tool",
                        tool_call_id=str(uuid.uuid4()),
                    ).model_dump(),
                )
                # 直接调用流式工具
                await self.handle_stream_output_step(
                    tool_arguments=stream_tool_arguments,
                    tool_history=final_tool_history,
                )
            _logger.warning("[MCPAgentExecutor] LLM未返回工具调用")
            self.task.state.executorStatus = ExecutorStatus.SUCCESS
            return []

        self._current_step_id = set()
        # 创建状态为WAITING的tool history
        pending_histories: list[ExecutorHistory] = []
        for tool_call in tool_calls:
            # 提前判断工具是否存在，确定状态和输出数据
            if tool_call.name not in self._tool_list:
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
            step_id = uuid.uuid4()
            self._current_step_id.add(step_id)
            history = ExecutorHistory(
                taskId=self.task.metadata.id,
                stepId=step_id,
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
                # 为流式输出提供间隙
                if tool_name == "stream_output":
                    await self._push_message(EventType.TEXT_ADD, "\n\n---\n\n")
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

    async def generate_and_save_abstract(
            self,
            record_id: uuid.UUID,
            current_history_for_abstract: list,
            language: LanguageType,
            llm: LLM,  # 根据llm实际类型标注
    ) -> bool:
        """
        独立的异步函数：生成摘要并入库
        :param record_id: 记录ID
        :param current_history_for_abstract: 生成摘要的历史记录
        :param language: 语言类型
        :param llm: LLM实例
        :return: 是否执行成功
        """  # noqa: D205
        try:
            # 1. 生成摘要
            _logger.debug("开始生成摘要，record_id=%s", record_id)
            abstract_output = await AbstractGenerator.generate(
                executor_history=current_history_for_abstract,
                record_id=record_id,
                language=language,
                llm=llm,
            )
            # 提取摘要文本（根据AbstractGenerator返回值调整）
            abstract_text = abstract_output.abstract if hasattr(abstract_output, "abstract") else str(abstract_output)

            # 2. 入库（创建/更新）
            success = await AbstractManager.create_or_update_abstract(
                record_id=record_id,
                abstract_text=abstract_text,

            )

            if success:
                _logger.info("摘要生成并入库成功，record_id=%s", record_id)

        except Exception:
            _logger.exception("异步生成/入库摘要失败，record_id=%s", record_id)
            return False

    async def run(self) -> None:
        """执行MCP Agent的主逻辑"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        # 选择工具
        _logger.info("[MCPAgentExecutor] 创建工具列表并选择工具")
        self._tool_list = await self.create_tool_list(query=self.question)

        _logger.info("[MCPAgentExecutor] _tool_list: %s", list(self._tool_list.keys()))
        _logger.info("[MCPAgentExecutor] 创建系统提示词")
        system_template = r"""
            {part.stream_output}
            {role.main}
            {part.todo}
            {part.final}
            {part.tool}
            {part.env}
        """
        self._system_prompt = self._prompt_mgmt.format(agent_metadata=self.app_metadata, template=system_template,
                                                       tools=self._tool_list)  # noqa: E501
        # 添加 user 消息
        await self._add_initial_user_message_if_needed()

        # 创建当前问询的历史记录用于摘要
        current_history_for_abstract = [self.task.context[-1]] if self.task.context else []

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
        # 生成摘要
        if current_history_for_abstract:
            non_stream_histories = [h for h in current_history_for_abstract if h.stepName != "stream_output"]
            records = await RecordManager.query_record_by_conversation_id(
                user_id=self.task.metadata.userId,
                conversation_id=self.task.metadata.conversationId,  # type: ignore  # noqa: PGH003
                total_pairs=1,
            )
            current_record = records[0]
            save_abstract = asyncio.create_task(  # noqa: RUF006
                self.generate_and_save_abstract(
                    record_id=current_record.id,
                    current_history_for_abstract=non_stream_histories,
                    language=self.task.runtime.language,
                    llm=self.llm,
                ),
            )

            def _handle_abstract_task_done(task: asyncio.Task):
                try:
                    task.result()  # 触发任务内的异常（如果有）
                except Exception as e:
                    _logger.error(
                        "后台摘要任务执行失败（回调兜底），record_id=%s",
                        current_record.id,
                        exc_info=e
                    )

            save_abstract.add_done_callback(_handle_abstract_task_done)
        # 运行结束清理MCP客户端
        for mcp_service in self._mcp_list:
            try:
                await mcp_pool.stop(mcp_service.id, self.task.metadata.userId)
            except Exception:
                _logger.exception("[MCPAgentExecutor] 停止MCP客户端时发生错误")
        self._save_checkpoint()
