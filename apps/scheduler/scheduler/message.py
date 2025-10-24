# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""消息推送相关的Mixin类"""

import logging

from apps.common.queue import MessageQueue
from apps.llm import LLMConfig
from apps.schemas.enum_var import EventType
from apps.schemas.task import TaskData

_logger = logging.getLogger(__name__)


class MessagingMixin:
    """处理消息推送相关的逻辑"""

    queue: MessageQueue
    task: TaskData
    llm: LLMConfig

    async def _push_done_message(self) -> None:
        """推送任务完成消息"""
        _logger.info("[Scheduler] 发送结束消息")
        await self.queue.push_output(self.task, self.llm, event_type=EventType.DONE.value, data={})
