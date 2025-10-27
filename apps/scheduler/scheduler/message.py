# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""消息推送相关的Mixin类"""

import logging
from typing import Any

from apps.common.queue import MessageQueue
from apps.llm import LLM
from apps.schemas.enum_var import EventType
from apps.schemas.task import TaskData

_logger = logging.getLogger(__name__)


class MessagingMixin:
    """处理消息推送相关的逻辑"""

    queue: MessageQueue
    task: TaskData
    llm: LLM

    async def _push_done_message(self) -> None:
        """推送任务完成消息"""
        _logger.info("[Scheduler] 发送结束消息")
        await self.queue.push_output(self.task, self.llm, event_type=EventType.DONE.value, data={})

    async def _push_executor_start_message(self, data: dict[str, Any] | None = None) -> None:
        """推送executor.start消息"""
        _logger.info("[Scheduler] 发送executor.start消息")
        if data is None:
            data = {}
        await self.queue.push_output(self.task, self.llm, event_type=EventType.EXECUTOR_START.value, data=data)

    async def _push_executor_stop_message(self, data: dict[str, Any] | None = None) -> None:
        """推送executor.stop消息"""
        _logger.info("[Scheduler] 发送executor.stop消息")
        if data is None:
            data = {}
        await self.queue.push_output(self.task, self.llm, event_type=EventType.EXECUTOR_STOP.value, data=data)
