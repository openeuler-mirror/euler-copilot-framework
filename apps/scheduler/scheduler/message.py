"""Scheduler消息推送

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import logging
from datetime import datetime, timezone
from textwrap import dedent
from typing import Union

import ray
from ray import actor

from apps.common.config import config
from apps.entities.collection import Document
from apps.entities.enum_var import EventType
from apps.entities.message import (
    DocumentAddContent,
    InitContent,
    InitContentFeature,
    TextAddContent,
)
from apps.entities.rag_data import RAGEventData, RAGQueryReq
from apps.entities.record import RecordDocument
from apps.entities.task import TaskBlock
from apps.service import RAG

logger = logging.getLogger("ray")


async def push_init_message(task: TaskBlock, queue: actor.ActorHandle, context_num: int, *, is_flow: bool = False) -> TaskBlock:
    """推送初始化消息"""
    # 组装feature
    if is_flow:
        feature = InitContentFeature(
            maxTokens=config["LLM_MAX_TOKENS"],
            contextNum=context_num,
            enableFeedback=False,
            enableRegenerate=False,
        )
    else:
        feature = InitContentFeature(
            maxTokens=config["LLM_MAX_TOKENS"],
            contextNum=context_num,
            enableFeedback=True,
            enableRegenerate=True,
        )

    # 保存必要信息到Task
    created_at = round(datetime.now(timezone.utc).timestamp(), 3)
    task.record.metadata.time_cost = created_at
    task.record.metadata.feature = feature.model_dump(exclude_none=True, by_alias=True)

    # 推送初始化消息
    await queue.push_output.remote( # type: ignore[attr-defined]
        task=task,
        event_type=EventType.INIT,
        data=InitContent(feature=feature, createdAt=created_at).model_dump(exclude_none=True, by_alias=True),
    )
    return task


async def push_rag_message(task: TaskBlock, queue: actor.ActorHandle, user_sub: str, rag_data: RAGQueryReq) -> TaskBlock:
    """推送RAG消息"""
    full_answer = ""
    task_actor = ray.get_actor("task")

    async for chunk in RAG.get_rag_result(user_sub, rag_data):
        task, chunk_content = await _push_rag_chunk(task, queue, chunk)
        full_answer += chunk_content
        # FIXME: 这里由于后面没有其他消息，所以只能每个trunk更新task
        await task_actor.set_task.remote(task.record.task_id, task)

    # 保存答案
    task.record.content.answer = full_answer
    return task


async def _push_rag_chunk(task: TaskBlock, queue: actor.ActorHandle, content: str) -> tuple[TaskBlock, str]:
    """推送RAG单个消息块"""
    # 如果是换行
    if not content or not content.rstrip().rstrip("\n"):
        return task, ""

    try:
        content_obj = RAGEventData.model_validate_json(dedent(content[6:]).rstrip("\n"))
        # 如果是空消息
        if not content_obj.content:
            return task, ""

        # 更新Token数量
        task.record.metadata.input_tokens = content_obj.input_tokens
        task.record.metadata.output_tokens = content_obj.output_tokens

        # 推送消息
        await queue.push_output.remote( # type: ignore[attr-defined]
            task=task,
            event_type=EventType.TEXT_ADD,
            data=TextAddContent(text=content_obj.content).model_dump(exclude_none=True, by_alias=True),
        )
        return task, content_obj.content
    except Exception:
        logger.exception("[Scheduler] RAG服务返回错误数据")
        return task, ""


async def push_document_message(task: TaskBlock, queue: actor.ActorHandle, doc: Union[RecordDocument, Document]) -> TaskBlock:
    """推送文档消息"""
    content = DocumentAddContent(
        documentId=doc.id,
        documentName=doc.name,
        documentType=doc.type,
        documentSize=round(doc.size, 2),
    )
    await queue.push_output.remote( # type: ignore[attr-defined]
        task=task,
        event_type=EventType.DOCUMENT_ADD,
        data=content.model_dump(exclude_none=True, by_alias=True),
    )
    return task
