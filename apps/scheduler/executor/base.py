# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Executor基类"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from apps.common.security import Security
from apps.schemas.enum_var import EventType
from apps.schemas.message import TextAddContent
from apps.schemas.record import RecordContent
from apps.schemas.scheduler import ExecutorBackground
from apps.services.record import RecordManager

if TYPE_CHECKING:
    from apps.common.queue import MessageQueue
    from apps.llm import LLMConfig
    from apps.schemas.task import TaskData


class BaseExecutor(BaseModel, ABC):
    """Executor基类"""

    task: "TaskData"
    msg_queue: "MessageQueue"
    llm: "LLMConfig"

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
        # 不存在conversationId，为首个问题
        if not self.task.metadata.conversationId:
            self.background = ExecutorBackground(
                conversation=[],
                facts=[],
                num=n,
            )
            return
        # 获取最后n+5条Record
        records = await RecordManager.query_record_by_conversation_id(
            self.task.metadata.userSub, self.task.metadata.conversationId, n + 5,
        )
        # 组装问答
        context = []
        facts = []
        for record in records:
            record_data = RecordContent.model_validate_json(Security.decrypt(record.content, record.key))
            context.append({
                "question": record_data.question,
                "answer": record_data.answer,
            })
            facts.extend(record_data.facts)
        self.background = ExecutorBackground(
            conversation=context,
            facts=facts,
            num=n,
        )

    async def _push_message(self, event_type: str, data: dict[str, Any] | str | None = None) -> None:
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

        await self.msg_queue.push_output(
            self.task,
            self.llm,
            event_type=event_type,
            data=data,
        )

    @abstractmethod
    async def run(self) -> None:
        """运行Executor"""
        raise NotImplementedError
