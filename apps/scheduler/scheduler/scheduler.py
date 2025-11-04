# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""调度器；负责任务的分发与执行"""

import asyncio
import logging
import uuid

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

        done, pending = await asyncio.wait(
            [main_task, monitor],
            return_when=asyncio.FIRST_COMPLETED,
        )

        if kill_event.is_set():
            await self._handle_task_cancellation(main_task)

        await self._push_done_message()
        await self.queue.close()
