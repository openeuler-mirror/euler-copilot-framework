# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""执行器相关的Mixin类"""

import asyncio
import logging
import uuid

from apps.common.queue import MessageQueue
from apps.llm import LLMConfig
from apps.models import AppType, ExecutorStatus
from apps.scheduler.executor.agent import MCPAgentExecutor
from apps.scheduler.executor.flow import FlowExecutor
from apps.scheduler.executor.qa import QAExecutor
from apps.scheduler.pool.pool import pool
from apps.schemas.request_data import RequestData
from apps.schemas.task import TaskData
from apps.services.activity import Activity
from apps.services.appcenter import AppCenterManager
from apps.services.conversation import ConversationManager

_logger = logging.getLogger(__name__)


class ExecutorMixin:
    """处理执行器相关的逻辑"""

    task: TaskData
    post_body: RequestData
    queue: MessageQueue
    llm: LLMConfig

    async def get_top_flow(self) -> str:
        """获取Top1 Flow (由FlowMixin实现)"""
        ...

    async def _determine_app_id(self) -> uuid.UUID | None:
        """确定最终使用的 app_id"""
        conversation = None

        if self.task.metadata.conversationId:
            conversation = await ConversationManager.get_conversation_by_conversation_id(
                self.task.metadata.userId,
                self.task.metadata.conversationId,
            )

        if conversation and conversation.appId:
            final_app_id = conversation.appId
            _logger.info("[Scheduler] 使用Conversation中的appId: %s", final_app_id)

            if self.post_body.app and self.post_body.app.app_id and self.post_body.app.app_id != conversation.appId:
                _logger.warning(
                    "[Scheduler] post_body中的app_id(%s)与Conversation中的appId(%s)不符，忽略post_body中的app信息",
                    self.post_body.app.app_id,
                    conversation.appId,
                )
                self.post_body.app.app_id = conversation.appId
        elif self.post_body.app and self.post_body.app.app_id:
            final_app_id = self.post_body.app.app_id
            _logger.info("[Scheduler] Conversation中无appId，使用post_body中的app_id: %s", final_app_id)
        else:
            final_app_id = None
            _logger.info("[Scheduler] Conversation和post_body中均无appId，fallback到智能问答")

        return final_app_id

    async def _create_executor_task(self, final_app_id: uuid.UUID | None) -> asyncio.Task | None:
        """
        根据 app_id 创建对应的执行器任务

        Args:
            final_app_id: 要使用的 app_id，None 表示使用 QA 模式

        Returns:
            创建的异步任务，如果发生错误则返回 None

        """
        if final_app_id is None:
            _logger.info("[Scheduler] 运行智能问答模式")
            return asyncio.create_task(self._run_qa())

        try:
            app_data = await AppCenterManager.fetch_app_metadata_by_id(final_app_id)
        except ValueError:
            _logger.exception("[Scheduler] App %s 不存在或元数据文件缺失", final_app_id)
            await self.queue.close()
            return None

        context_num = app_data.history_len
        _logger.info("[Scheduler] App上下文窗口: %d", context_num)

        if app_data.app_type == AppType.FLOW:
            _logger.info("[Scheduler] 运行Flow应用")
            return asyncio.create_task(self._run_flow())

        _logger.info("[Scheduler] 运行MCP Agent应用")
        return asyncio.create_task(self._run_agent())

    async def _handle_task_cancellation(self, main_task: asyncio.Task) -> None:
        """
        处理任务取消的逻辑

        Args:
            main_task: 需要取消的主任务

        """
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

    async def _monitor_activity(self, kill_event: asyncio.Event, user_id: str) -> None:
        """监控用户活动状态，不活跃时终止工作流"""
        try:
            check_interval = 0.5

            while not kill_event.is_set():
                is_active = await Activity.is_active(user_id)

                if not is_active:
                    _logger.warning("[Scheduler] 用户 %s 不活跃，终止工作流", user_id)
                    kill_event.set()
                    break

                await asyncio.sleep(check_interval)
        except asyncio.CancelledError:
            _logger.info("[Scheduler] 活动监控任务已取消")
        except Exception:
            _logger.exception("[Scheduler] 活动监控过程中发生错误")
            kill_event.set()

    async def _run_qa(self) -> None:
        """运行QA执行器"""
        qa_executor = QAExecutor(
            task=self.task,
            msg_queue=self.queue,
            question=self.post_body.question,
            llm=self.llm,
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
        )
        _logger.info("[Scheduler] 运行MCP执行器")
        await agent_exec.init()
        await agent_exec.run()
        self.task = agent_exec.task
