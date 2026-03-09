# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Executor基类"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict

from apps.common.queue import MessageQueue
from apps.llm import LLM
from apps.schemas.enum_var import EventType
from apps.schemas.flow import AgentAppMetadata, FlowAppMetadata
from apps.schemas.message import TextAddContent
from apps.schemas.scheduler import ExecutorBackground
from apps.schemas.task import TaskData
from apps.services.record import RecordManager

_logger = logging.getLogger(__name__)


class BaseExecutor(BaseModel, ABC):
    """Executor基类"""

    task: TaskData
    msg_queue: MessageQueue
    llm: LLM
    app_metadata: FlowAppMetadata | AgentAppMetadata | None = None

    question: str

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    @abstractmethod
    async def init(self) -> None:
        """初始化Executor"""
        raise NotImplementedError

    async def _load_history(self, n: int = 3) -> None:
        """加载历史记录"""
        if not self.task.metadata.conversationId:
            self.background = ExecutorBackground(
                conversation=[],
                facts=[],
                history_questions=[],
                num=n,
            )
            return
        records = await RecordManager.query_record_by_conversation_id(
            self.task.metadata.userId, self.task.metadata.conversationId, n + 10,
        )
        context = []
        facts = []
        history_questions = []
        for i, record in enumerate(records):
            if i < n:
                context.extend([
                    {
                        "role": "user",
                        "content": record.content.question,
                    },
                    {
                        "role": "assistant",
                        "content": record.content.answer,
                    },
                ])
            if i < n + 5:
                facts.extend(record.content.facts)
            history_questions.append(record.content.question)
        self.background = ExecutorBackground(
            conversation=context,
            facts=facts,
            history_questions=history_questions,
            num=n,
        )

    async def _push_message(self, event_type: str, data: dict[str, Any] | str | None = None) -> None:
        """
        统一的消息推送接口

        :param event_type: 事件类型
        :param data: 消息数据，如果是EXECUTOR_START事件且data为None，则自动构建ExecutorStartContent
        """
        if event_type == EventType.TEXT_ADD.value and isinstance(data, str):
            data = TextAddContent(text=data).model_dump(exclude_none=True, by_alias=True)

        if data is None:
            data = {}
        elif isinstance(data, str):
            data = TextAddContent(text=data).model_dump(exclude_none=True, by_alias=True)

        await self.msg_queue.push_output(
            self.task,
            self.llm,
            event_type=event_type,
            data=data,
        )

    async def _check_cancelled(self) -> None:
        """
        检查当前任务是否已被取消，如果已取消则抛出CancelledError

        :raises asyncio.CancelledError: 当任务已被取消时
        """
        try:
            await asyncio.sleep(0)
        except asyncio.CancelledError:
            _logger.warning("[%s] 检测到取消信号，终止执行", self.__class__.__name__)
            raise

    @abstractmethod
    async def run(self) -> None:
        """运行Executor"""
        raise NotImplementedError
