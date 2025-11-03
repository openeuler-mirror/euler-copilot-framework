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
    enable_thinking: bool = False,
) -> None:
    """推送RAG消息"""
    full_answer = ""
    error_message = None
    
    try:
        async for chunk in RAG.chat_with_llm_base_on_rag(
            user_sub, llm, history, doc_ids, rag_data, task.language, enable_thinking
        ):
            try:
                task, content_obj = await _push_rag_chunk(task, queue, chunk)
                if content_obj and hasattr(content_obj, 'event_type'):
                    if content_obj.event_type == EventType.TEXT_ADD.value:
                        # 如果是文本消息，直接拼接到答案中
                        full_answer += content_obj.content
                    elif content_obj.event_type == EventType.DOCUMENT_ADD.value:
                        task.runtime.documents.append(content_obj.content)
            except Exception as chunk_error:
                logger.error(f"[Scheduler] 处理RAG消息块失败: {chunk_error}")
                # 继续处理其他块，不中断整个流程
                continue
        
        if full_answer.strip():
            task.state.flow_status = FlowStatus.SUCCESS
        else:
            logger.warning("[Scheduler] RAG服务返回空响应")
            task.state.flow_status = FlowStatus.ERROR
            error_message = "RAG服务返回空响应"
            
    except ValueError as e:
        # 这通常是LLM相关的错误（如API认证、余额不足等）
        logger.error(f"[Scheduler] RAG服务参数错误: {e}")
        task.state.flow_status = FlowStatus.ERROR
        error_message = str(e)
        
        # 推送错误消息到前端
        try:
            from apps.schemas.message import TextAddContent
            await queue.push_output(
                task=task,
                event_type=EventType.TEXT_ADD.value,
                data=TextAddContent(text=f"❌ 错误: {error_message}").model_dump(exclude_none=True, by_alias=True),
            )
        except Exception as push_error:
            logger.error(f"[Scheduler] 推送错误消息失败: {push_error}")
            
    except ConnectionError as e:
        logger.error(f"[Scheduler] RAG服务连接失败: {e}")
        task.state.flow_status = FlowStatus.ERROR
        error_message = "RAG服务连接失败，请检查网络连接"
        
    except TimeoutError as e:
        logger.error(f"[Scheduler] RAG服务超时: {e}")
        task.state.flow_status = FlowStatus.ERROR
        error_message = "RAG服务响应超时，请稍后重试"
        
    except Exception as e:
        logger.error(f"[Scheduler] RAG服务发生未知错误: {e}")
        task.state.flow_status = FlowStatus.ERROR
        error_message = f"RAG服务发生未知错误: {e}"
        
    # 如果有错误，确保错误信息被保存
    if error_message and not full_answer:
        full_answer = f"错误: {error_message}"
        
    # 保存答案和任务状态
    task.runtime.answer = full_answer
    task.tokens.full_time = round(datetime.now(UTC).timestamp(), 2) - task.tokens.time
    
    try:
        await TaskManager.save_task(task.id, task)
    except Exception as save_error:
        logger.error(f"[Scheduler] 保存任务失败: {save_error}")
        # 任务保存失败不应该影响主流程


async def _push_rag_chunk(task: Task, queue: MessageQueue, content: str) -> tuple[Task, RAGEventData | None]:
    """推送RAG单个消息块"""
    # 如果是换行或空内容
    if not content or not content.rstrip().rstrip("\n"):
        return task, None

    try:
        # 解析RAG事件数据
        if len(content) < 6:
            logger.warning("[Scheduler] RAG消息块内容过短: %s", content)
            return task, None
            
        raw_content = dedent(content[6:]).rstrip("\n")
        if not raw_content.strip():
            logger.debug("[Scheduler] RAG消息块为空")
            return task, None
            
        try:
            content_obj = RAGEventData.model_validate_json(raw_content)
        except Exception as parse_error:
            logger.error("[Scheduler] RAG事件数据解析失败: %s, 原始内容: %s", parse_error, raw_content[:100])
            return task, None
        
        # 如果是空消息
        if not content_obj.content:
            logger.debug("[Scheduler] RAG事件内容为空")
            return task, None

        # 更新token统计
        if hasattr(content_obj, 'input_tokens') and content_obj.input_tokens is not None:
            task.tokens.input_tokens = content_obj.input_tokens
        if hasattr(content_obj, 'output_tokens') and content_obj.output_tokens is not None:
            task.tokens.output_tokens = content_obj.output_tokens

        # 保存任务状态
        try:
            await TaskManager.save_task(task.id, task)
        except Exception as save_error:
            logger.warning("[Scheduler] 保存任务状态失败: %s", save_error)
            # 保存失败不应该阻止消息推送
        
        # 推送消息到前端
        try:
            if content_obj.event_type == EventType.TEXT_ADD.value:
                await queue.push_output(
                    task=task,
                    event_type=content_obj.event_type,
                    data=TextAddContent(text=content_obj.content).model_dump(exclude_none=True, by_alias=True),
                )
            elif content_obj.event_type == EventType.DOCUMENT_ADD.value:
                if isinstance(content_obj.content, dict):
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
                            createdAt=round(content_obj.content.get("created_at", datetime.now(tz=UTC).timestamp()), 3),
                        ).model_dump(exclude_none=True, by_alias=True),
                    )
                else:
                    logger.warning("[Scheduler] DOCUMENT_ADD事件内容格式错误: %s", type(content_obj.content))
            else:
                logger.warning("[Scheduler] 未知的事件类型: %s", content_obj.event_type)
                
        except Exception as push_error:
            logger.error("[Scheduler] 推送消息到前端失败: %s", push_error)
            # 推送失败不应该阻止返回结果
            
        return task, content_obj
        
    except Exception as e:
        logger.error("[Scheduler] 处理RAG消息块时发生未知错误: %s, 内容: %s", e, content[:100] if content else "None")
        return task, None