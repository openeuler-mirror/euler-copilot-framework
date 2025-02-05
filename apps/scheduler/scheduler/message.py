"""Scheduler消息推送

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from datetime import datetime, timezone
from textwrap import dedent
from typing import Union

from apps.common.queue import MessageQueue
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
from apps.manager import TaskManager
from apps.service import RAG


async def push_init_message(task_id: str, queue: MessageQueue, post_body: RequestData,  *, is_flow: bool = False) -> None:
    """推送初始化消息"""
    # 拿到Task
    task = await TaskManager.get_task(task_id)
    if not task:
        err = "[Scheduler] Task not found"
        raise ValueError(err)

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
    await TaskManager.set_task(task_id, task)

    # 推送初始化消息
    await queue.push_output(event_type=EventType.INIT, data=InitContent(feature=feature, createdAt=created_at).model_dump(exclude_none=True, by_alias=True))


async def push_rag_message(task_id: str, queue: MessageQueue, user_sub: str, rag_data: RAGQueryReq) -> None:
    """推送RAG消息"""
    task = await TaskManager.get_task(task_id)
    if not task:
        err = "Task not found"
        raise ValueError(err)

    rag_input_tokens = 0
    rag_output_tokens = 0
    full_answer = ""

    async for chunk in RAG.get_rag_result(user_sub, rag_data):
        chunk_content, rag_input_tokens, rag_output_tokens = await _push_rag_chunk(task_id, queue, chunk, rag_input_tokens, rag_output_tokens)
        full_answer += chunk_content

    # 保存答案
    task.record.content.answer = full_answer
    await TaskManager.set_task(task_id, task)


async def _push_rag_chunk(task_id: str, queue: MessageQueue, content: str, rag_input_tokens: int, rag_output_tokens: int) -> tuple[str, int, int]:
    """推送RAG单个消息块"""
    # 如果是换行
    if not content or not content.rstrip().rstrip("\n"):
        return "", rag_input_tokens, rag_output_tokens

    try:
        content_obj = RAGEventData.model_validate_json(dedent(content[6:]).rstrip("\n"))
        # 如果是空消息
        if not content_obj.content:
            return "", rag_input_tokens, rag_output_tokens

        # 计算Token数量
        delta_input_tokens = content_obj.input_tokens - rag_input_tokens
        delta_output_tokens = content_obj.output_tokens - rag_output_tokens
        await TaskManager.update_token_summary(task_id, delta_input_tokens, delta_output_tokens)
        # 更新Token的值
        rag_input_tokens = content_obj.input_tokens
        rag_output_tokens = content_obj.output_tokens

        # 推送消息
        await queue.push_output(event_type=EventType.TEXT_ADD, data=TextAddContent(text=content_obj.content).model_dump(exclude_none=True, by_alias=True))
        return content_obj.content, rag_input_tokens, rag_output_tokens
    except Exception as e:
        LOGGER.error(f"[Scheduler] RAG服务返回错误数据: {e!s}\n{content}")
        return "", rag_input_tokens, rag_output_tokens


async def push_document_message(queue: MessageQueue, doc: Union[RecordDocument, Document]) -> None:
    """推送文档消息"""
    content = DocumentAddContent(
        documentId=doc.id,
        documentName=doc.name,
        documentType=doc.type,
        documentSize=round(doc.size, 2),
    )
    await queue.push_output(event_type=EventType.DOCUMENT_ADD, data=content.model_dump(exclude_none=True, by_alias=True))
