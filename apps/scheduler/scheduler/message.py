"""Scheduler消息推送

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from datetime import datetime, timezone
from textwrap import dedent
from typing import Union

import ray

from apps.constants import LOGGER
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
from apps.entities.request_data import RequestData
from apps.entities.task import TaskBlock
from apps.service import RAG


async def push_init_message(task_id: str, queue: ray.ObjectRef, post_body: RequestData,  *, is_flow: bool = False) -> None:
    """推送初始化消息"""
    task_actor = ray.get_actor("task")
    task: TaskBlock = await task_actor.get_task.remote(task_id)
    # 组装feature
    if is_flow:
        feature = InitContentFeature(
            maxTokens=post_body.features.max_tokens,
            contextNum=post_body.features.context_num,
            enableFeedback=False,
            enableRegenerate=False,
        )
    else:
        feature = InitContentFeature(
            maxTokens=post_body.features.max_tokens,
            contextNum=post_body.features.context_num,
            enableFeedback=True,
            enableRegenerate=True,
        )

    # 保存必要信息到Task
    created_at = round(datetime.now(timezone.utc).timestamp(), 2)
    task.record.metadata.time = created_at
    task.record.metadata.feature = feature.model_dump(exclude_none=True, by_alias=True)

    # 推送初始化消息
    await queue.push_output.remote( # type: ignore[attr-defined]
        task=task,
        event_type=EventType.INIT,
        data=InitContent(feature=feature, createdAt=created_at).model_dump(exclude_none=True, by_alias=True),
    )
    await task_actor.set_task.remote(task_id, task)


async def push_rag_message(task_id: str, queue: ray.ObjectRef, user_sub: str, rag_data: RAGQueryReq) -> None:
    """推送RAG消息"""
    task_actor = ray.get_actor("task")
    full_answer = ""

    async for chunk in RAG.get_rag_result(user_sub, rag_data):
        chunk_content = await _push_rag_chunk(task_id, queue, chunk)
        full_answer += chunk_content

    # 保存答案
    task: TaskBlock = await task_actor.get_task.remote(task_id)
    task.record.content.answer = full_answer
    await task_actor.set_task.remote(task_id, task)


async def _push_rag_chunk(task_id: str, queue: ray.ObjectRef, content: str) -> str:
    """推送RAG单个消息块"""
    task_actor = ray.get_actor("task")
    task: TaskBlock = await task_actor.get_task.remote(task_id)
    # 如果是换行
    if not content or not content.rstrip().rstrip("\n"):
        return ""

    try:
        content_obj = RAGEventData.model_validate_json(dedent(content[6:]).rstrip("\n"))
        # 如果是空消息
        if not content_obj.content:
            return ""

        # 更新Token数量
        task.record.metadata.input_tokens = content_obj.input_tokens
        task.record.metadata.output_tokens = content_obj.output_tokens

        # 推送消息
        await queue.push_output.remote( # type: ignore[attr-defined]
            task=task,
            event_type=EventType.TEXT_ADD,
            data=TextAddContent(text=content_obj.content).model_dump(exclude_none=True, by_alias=True),
        )
        await task_actor.set_task.remote(task_id, task)
        return content_obj.content
    except Exception as e:
        LOGGER.error(f"[Scheduler] RAG服务返回错误数据: {e!s}\n{content}")
        return ""


async def push_document_message(task_id: str, queue: ray.ObjectRef, doc: Union[RecordDocument, Document]) -> None:
    """推送文档消息"""
    task_actor = ray.get_actor("task")
    task: TaskBlock = await task_actor.get_task.remote(task_id)
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
    await task_actor.set_task.remote(task_id, task)
