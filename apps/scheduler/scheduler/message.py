# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Scheduler消息推送"""

import logging
from datetime import UTC, datetime
from textwrap import dedent

from apps.common.config import Config
from apps.common.queue import MessageQueue
from apps.schemas.collection import LLM, Document
from apps.schemas.enum_var import EventType
from apps.schemas.message import (
    DocumentAddContent,
    InitContent,
    InitContentFeature,
    TextAddContent,
)
from apps.schemas.enum_var import FlowStatus
from apps.schemas.rag_data import RAGEventData, RAGQueryReq
from apps.schemas.record import RecordDocument
from apps.schemas.task import Task
from apps.services.rag import RAG
from apps.services.task import TaskManager

logger = logging.getLogger(__name__)


async def push_init_message(
    task: Task, queue: MessageQueue, context_num: int, *, is_flow: bool = False,
) -> Task:
    """推送初始化消息"""
    # 组装feature
    if is_flow:
        feature = InitContentFeature(
            maxTokens=Config().get_config().llm.max_tokens or 0,
            contextNum=context_num,
            enableFeedback=False,
            enableRegenerate=False,
        )
    else:
        feature = InitContentFeature(
            maxTokens=Config().get_config().llm.max_tokens or 0,
            contextNum=context_num,
            enableFeedback=True,
            enableRegenerate=True,
        )

    # 保存必要信息到Task
    created_at = round(datetime.now(UTC).timestamp(), 3)
    task.tokens.time = created_at

    await TaskManager.save_task(task.id, task)
    # 推送初始化消息
    await queue.push_output(
        task=task,
        event_type=EventType.INIT.value,
        data=InitContent(feature=feature, createdAt=created_at).model_dump(exclude_none=True, by_alias=True),
    )
    return task


async def push_rag_message(
    task: Task,
    queue: MessageQueue,
    user_sub: str,
    llm: LLM,
    history: list[dict[str, str]],
    doc_ids: list[str],
    rag_data: RAGQueryReq,
) -> None:
    """推送RAG消息"""
    full_answer = ""
    try:
        async for chunk in RAG.chat_with_llm_base_on_rag(
            user_sub, llm, history, doc_ids, rag_data, task.language
        ):
            task, content_obj = await _push_rag_chunk(task, queue, chunk)
            if content_obj.event_type == EventType.TEXT_ADD.value:
                # 如果是文本消息，直接拼接到答案中
                full_answer += content_obj.content
            elif content_obj.event_type == EventType.DOCUMENT_ADD.value:
                task.runtime.documents.append(content_obj.content)
        task.state.flow_status = FlowStatus.SUCCESS
    except Exception as e:
        logger.error(f"[Scheduler] RAG服务发生错误: {e}")
        task.state.flow_status = FlowStatus.ERROR
    # 保存答案
    task.runtime.answer = full_answer
    task.tokens.full_time = round(datetime.now(UTC).timestamp(), 2) - task.tokens.time
    await TaskManager.save_task(task.id, task)


async def _push_rag_chunk(task: Task, queue: MessageQueue, content: str) -> tuple[Task, RAGEventData]:
    """推送RAG单个消息块"""
    # 如果是换行
    if not content or not content.rstrip().rstrip("\n"):
        return task, ""

    try:
        content_obj = RAGEventData.model_validate_json(dedent(content[6:]).rstrip("\n"))
        # 如果是空消息
        if not content_obj.content:
            return task, ""

        task.tokens.input_tokens = content_obj.input_tokens
        task.tokens.output_tokens = content_obj.output_tokens

        await TaskManager.save_task(task.id, task)
        # 推送消息
        if content_obj.event_type == EventType.TEXT_ADD.value:
            await queue.push_output(
                task=task,
                event_type=content_obj.event_type,
                data=TextAddContent(text=content_obj.content).model_dump(exclude_none=True, by_alias=True),
            )
        elif content_obj.event_type == EventType.DOCUMENT_ADD.value:
            await queue.push_output(
                task=task,
                event_type=content_obj.event_type,
                data=DocumentAddContent(
                    documentId=content_obj.content.get("id", ""),
                    documentOrder=content_obj.content.get("order", 0),
                    documentAuthor=content_obj.content.get("author", ""),
                    documentName=content_obj.content.get("name", ""),
                    documentAbstract=content_obj.content.get("abstract", ""),
                    documentType=content_obj.content.get("extension", ""),
                    documentSize=content_obj.content.get("size", 0),
                    createdAt=round(datetime.now(tz=UTC).timestamp(), 3),
                ).model_dump(exclude_none=True, by_alias=True),
            )
    except Exception:
        logger.exception("[Scheduler] RAG服务返回错误数据")
        return task, ""
    else:
        return task, content_obj
