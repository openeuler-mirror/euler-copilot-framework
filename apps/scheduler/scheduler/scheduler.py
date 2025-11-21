# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""调度器；负责任务的分发与执行"""

import asyncio
import contextlib
import logging

from apps.common.queue import MessageQueue
from apps.schemas.request_data import RequestData

from .data import DataMixin
from .executor import ExecutorMixin
from .flow import FlowMixin
from .init import InitMixin
from .message import MessageMixin
from .util import UtilMixin

_logger = logging.getLogger(__name__)


class Scheduler(
    InitMixin,
    ExecutorMixin,
    FlowMixin,
    DataMixin,
    MessageMixin,
    UtilMixin,
):
    """
    "调度器"，是最顶层的、控制Executor执行顺序和状态的逻辑。

    Scheduler包含一个"SchedulerContext"，作用为多个Executor的"聊天会话"

    所有属性都继承自各个Mixin类，主要包括：
    - task: TaskData (来自InitMixin)
    - llm: LLMConfig (来自InitMixin)
    - queue: MessageQueue (来自InitMixin)
    - post_body: RequestData (来自InitMixin)
    - user: User (来自InitMixin)
    - _env: SandboxedEnvironment (来自InitMixin)
    """

    async def init(
            self,
            queue: MessageQueue,
            post_body: RequestData,
            user_id: str,
            auth_header: str,
    ) -> None:
        """初始化"""
        self.queue = queue
        self.post_body = post_body

        await self._get_user(user_id)
        await self._init_task(user_id, auth_header)
        self._init_jinja2_env()
        self.llm = await self._get_scheduler_llm(post_body.llm_id)

    async def run(self) -> None:
        """运行调度器"""
        _logger.info("[Scheduler] 开始执行")

        kill_event = asyncio.Event()
        monitor = asyncio.create_task(self._monitor_activity(kill_event, self.task.metadata.userId))

        final_app_id = await self._determine_app_id()

        main_task = await self._create_executor_task(final_app_id)
        if main_task is None:
            return

        await self._push_executor_start_message()

        while not main_task.done() and not monitor.done():
            if kill_event.is_set():
                await self._handle_task_cancellation(main_task)
                monitor.cancel()
                break

            done, _ = await asyncio.wait(
                [main_task, monitor],
                timeout=0.1,  # 100ms检查一次
                return_when=asyncio.FIRST_COMPLETED,
            )

            if done:
                break

        if kill_event.is_set() and not main_task.done():
            await self._handle_task_cancellation(main_task)
        if not monitor.done():
            monitor.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await monitor

        await self._check_and_handle_executor_result()

        if not self.task.metadata.conversationId:
            _logger.info("[Scheduler] 创建新对话")
            title = self.task.runtime.userInput[:50] if self.task.runtime.userInput else "新对话"
            app_id = self.post_body.app.app_id if self.post_body.app else None

            try:
                await self._create_new_conversation(
                    title=title,
                    user_id=self.task.metadata.userId,
                    app_id=app_id,
                    debug=False,
                )
            except Exception:
                _logger.exception("[Scheduler] 创建Conversation失败")

        await self._push_executor_stop_message()
        await self._push_done_message()
        await self.queue.close()
