# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Executor基类"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict

from apps.common.queue import MessageQueue
from apps.schemas.enum_var import EventType
from apps.schemas.message import FlowStartContent, TextAddContent
from apps.schemas.scheduler import ExecutorBackground
from apps.schemas.task import Task

logger = logging.getLogger(__name__)


class BaseExecutor(BaseModel, ABC):
    """Executor基类"""

    task: Task
    msg_queue: MessageQueue
    background: ExecutorBackground
    question: str

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    @staticmethod
    def validate_flow_state(task: Task) -> None:
        """验证flow_state是否存在"""
        if not task.state:
            err = "[Executor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

    async def push_message(self, event_type: str, data: dict[str, Any] | str | None = None) -> None:
        """
        统一的消息推送接口

        :param event_type: 事件类型
        :param data: 消息数据，如果是FLOW_START事件且data为None，则自动构建FlowStartContent
        """        
        if event_type == EventType.TEXT_ADD.value and isinstance(data, str):
            data = TextAddContent(text=data).model_dump(exclude_none=True, by_alias=True)

        if data is None:
            data = {}
        elif isinstance(data, str):
            data = TextAddContent(text=data).model_dump(exclude_none=True, by_alias=True)

        logger.info(f"[BaseExecutor] 调用msg_queue.push_output - event_type: {event_type}")
        try:
            await self.msg_queue.push_output(
                self.task,
                event_type=event_type,
                data=data, # type: ignore[arg-type]
            )
            logger.info(f"[BaseExecutor] msg_queue.push_output调用成功 - event_type: {event_type}")
        except Exception as e:
            logger.error(f"[BaseExecutor] msg_queue.push_output调用失败 - event_type: {event_type}, error: {e}")
            raise

    @abstractmethod
    async def run(self) -> None:
        """运行Executor"""
        raise NotImplementedError
