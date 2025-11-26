# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""执行器相关的Mixin类"""

import asyncio
import logging
import uuid

from apps.common.queue import MessageQueue
from apps.llm import LLM
from apps.models import AppType, ExecutorStatus
from apps.scheduler.executor.agent import MCPAgentExecutor
from apps.scheduler.executor.flow import FlowExecutor
from apps.scheduler.executor.qa import QAExecutor
from apps.scheduler.pool.pool import pool
from apps.schemas.flow import AgentAppMetadata, FlowAppMetadata
from apps.schemas.request_data import RequestData
from apps.schemas.task import TaskData
from apps.services.appcenter import AppCenterManager

_logger = logging.getLogger(__name__)


class ExecutorMixin:
    """处理执行器相关的逻辑"""

    task: TaskData
    post_body: RequestData
    queue: MessageQueue
    llm: LLM
    app_metadata: FlowAppMetadata | AgentAppMetadata | None

    async def get_top_flow(self) -> str:
        """获取Top1 Flow (由FlowMixin实现)"""
        ...  # noqa: PIE790

    async def _create_executor_task(self, final_app_id: uuid.UUID | None) -> asyncio.Task | None:
        """根据 app_id 创建对应的执行器任务"""
        if final_app_id is None:
            _logger.info("[Scheduler] 运行智能问答模式")
            self.app_metadata = None
            return asyncio.create_task(self._run_qa())

        try:
            app_data = await AppCenterManager.fetch_app_metadata_by_id(final_app_id)
        except ValueError:
            _logger.exception("[Scheduler] App %s 不存在或元数据文件缺失", final_app_id)
            await self.queue.close()
            return None

        self.app_metadata = app_data
        context_num = app_data.history_len
        _logger.info("[Scheduler] App上下文窗口: %d", context_num)

        if app_data.app_type == AppType.FLOW:
            _logger.info("[Scheduler] 运行Flow应用")
            return asyncio.create_task(self._run_flow())

        _logger.info("[Scheduler] 运行MCP Agent应用")
        return asyncio.create_task(self._run_agent())

    async def _handle_task_cancellation(self, main_task: asyncio.Task) -> None:
        """处理任务取消的逻辑"""
        _logger.warning("[Scheduler] 用户取消执行，正在终止...")
        main_task.cancel()
        try:
            await main_task
        except asyncio.CancelledError:
            _logger.info("[Scheduler] 主任务已取消")
        except Exception:
            _logger.exception("[Scheduler] 终止工作流时发生错误")

        if self.task.state and self.task.state.executorStatus in [
            ExecutorStatus.INIT,
            ExecutorStatus.RUNNING,
            ExecutorStatus.WAITING,
        ]:
            self.task.state.executorStatus = ExecutorStatus.CANCELLED
            _logger.info("[Scheduler] ExecutorStatus已设置为CANCELLED")
        elif self.task.state:
            _logger.info("[Scheduler] ExecutorStatus为 %s，保持不变", self.task.state.executorStatus)
        else:
            _logger.warning("[Scheduler] task.state为None，无法更新ExecutorStatus")

    async def _run_qa(self) -> None:
        """运行QA执行器"""
        qa_executor = QAExecutor(
            task=self.task,
            msg_queue=self.queue,
            question=self.post_body.question,
            llm=self.llm,
            app_metadata=self.app_metadata,
        )
        _logger.info("[Scheduler] 开始智能问答")
        await qa_executor.init()
        await qa_executor.run()
        self.task = qa_executor.task

    async def _run_flow(self) -> None:
        """运行Flow执行器"""
        if not self.post_body.app or not self.post_body.app.app_id:
            _logger.error("[Scheduler] 未选择应用")
            return

        _logger.info("[Scheduler] 获取工作流元数据")
        flow_info = await pool.get_flow_metadata(self.post_body.app.app_id)

        if not flow_info:
            _logger.error("[Scheduler] 未找到工作流元数据")
            return

        if not self.post_body.app.flow_id:
            _logger.info("[Scheduler] 选择最合适的流")
            flow_id = await self.get_top_flow()
        else:
            flow_id = self.post_body.app.flow_id
        _logger.info("[Scheduler] 获取工作流定义")
        flow_data = await pool.get_flow(self.post_body.app.app_id, flow_id)

        if not flow_data:
            _logger.error("[Scheduler] 未找到工作流定义")
            return

        flow_exec = FlowExecutor(
            flow_id=flow_id,
            flow=flow_data,
            task=self.task,
            msg_queue=self.queue,
            question=self.post_body.question,
            post_body_app=self.post_body.app,
            llm=self.llm,
            app_metadata=self.app_metadata,
        )

        _logger.info("[Scheduler] 运行工作流执行器")
        await flow_exec.init()
        await flow_exec.run()
        self.task = flow_exec.task

    async def _run_agent(self) -> None:
        """构造Executor并执行"""
        if not self.post_body.app or not self.post_body.app.app_id:
            _logger.error("[Scheduler] 未选择MCP应用")
            return

        agent_exec = MCPAgentExecutor(
            task=self.task,
            msg_queue=self.queue,
            question=self.post_body.question,
            agent_id=self.post_body.app.app_id,
            params=self.post_body.app.params,
            llm=self.llm,
            app_metadata=self.app_metadata,
        )
        _logger.info("[Scheduler] 运行MCP执行器")
        await agent_exec.init()
        await agent_exec.run()
        self.task = agent_exec.task
