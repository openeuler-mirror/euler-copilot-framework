# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""上下文管理"""

import logging
from datetime import UTC, datetime
import re

from apps.common.security import Security
from apps.llm.patterns.facts import Facts
from apps.schemas.collection import Document
from apps.schemas.enum_var import StepStatus
from apps.schemas.record import (
    Record,
    RecordContent,
    RecordDocument,
    RecordGroupDocument,
    FootNoteMetaData,
    RecordMetadata,
)
from apps.schemas.request_data import RequestData
from apps.schemas.task import Task
from apps.services.appcenter import AppCenterManager
from apps.services.document import DocumentManager
from apps.services.record import RecordManager
from apps.services.task import TaskManager

logger = logging.getLogger(__name__)


async def get_docs(user_sub: str, post_body: RequestData) -> tuple[list[RecordDocument] | list[Document], list[str]]:
    """获取当前问答可供关联的文档"""
    if not post_body.group_id:
        err = "[Scheduler] 问答组ID不能为空！"
        logger.error(err)
        raise ValueError(err)

    doc_ids = []

    docs = await DocumentManager.get_used_docs_by_record_group(user_sub, post_body.group_id, type="question")
    if not docs:
        # 是新提问
        # 从Conversation中获取刚上传的文档
        docs = await DocumentManager.get_unused_docs(user_sub, post_body.conversation_id)
        # 从最近10条Record中获取文档
        docs += await DocumentManager.get_used_docs(user_sub, post_body.conversation_id, 10, type="question")
        doc_ids += [doc.id for doc in docs]
    else:
        # 是重新生成
        doc_ids += [doc.id for doc in docs]
    # 由于文档可能来自于外部
    return docs, doc_ids


async def assemble_history(history: list[dict[str, str]]) -> str:
    """
    组装历史问题

    :param history: 历史问题列表
    :return: 组装后的字符串
    """
    history_str = ""
    for item in history:
        role = item.get("role")
        content = item.get("content")
        if role and content:
            history_str += f"{role}: {content}\n"
    return history_str.strip()


async def get_context(user_sub: str, post_body: RequestData, n: int) -> tuple[list[dict[str, str]], list[str]]:
    """
    获取当前问答的上下文信息

    注意：这里的n要比用户选择的多，因为要考虑事实信息和历史问题
    """
    # 最多15轮
    n = min(n, 15)

    # 获取最后n+5条Record
    records = await RecordManager.query_record_by_conversation_id(user_sub, post_body.conversation_id, n + 5)

    # 组装问答
    context = []
    facts = []
    for record in records:
        record_data = RecordContent.model_validate_json(Security.decrypt(record.content, record.key))
        context.append({"role": "user", "content": record_data.question})
        context.append({"role": "assistant", "content": record_data.answer})
        facts.extend(record_data.facts)

    return context, facts


async def generate_facts(task: Task, question: str) -> tuple[Task, list[str]]:
    """生成Facts"""
    message = [
        {"role": "user", "content": question},
        {"role": "assistant", "content": task.runtime.answer},
    ]

    facts = await Facts().generate(conversation=message)
    task.runtime.facts = facts
    await TaskManager.save_task(task.id, task)

    return task, facts


async def save_data(task: Task, user_sub: str, post_body: RequestData) -> None:
    """保存当前Executor、Task、Record等的数据"""
    # 构造RecordContent
    used_docs = []
    order_to_id = {}
    for docs in task.runtime.documents:
        used_docs.append(
            RecordGroupDocument(
                _id=docs["id"],
                author=docs.get("author", ""),
                order=docs.get("order", 0),
                name=docs["name"],
                abstract=docs.get("abstract", ""),
                extension=docs.get("extension", ""),
                size=docs.get("size", 0),
                associated="answer",
                created_at=docs.get("created_at", round(datetime.now(UTC).timestamp(), 3)),
            )
        )
        if docs.get("order") is not None:
            order_to_id[docs["order"]] = docs["id"]

    foot_note_pattern = re.compile(r"\[\[(\d+)\]\]")
    foot_note_metadata_list = []
    offset = 0
    for match in foot_note_pattern.finditer(task.runtime.answer):
        order = int(match.group(1))
        if order in order_to_id:
            # 计算移除脚注后的插入位置
            original_start = match.start()
            new_position = original_start - offset

            foot_note_metadata_list.append(
                FootNoteMetaData(
                    releatedId=order_to_id[order],
                    insertPosition=new_position,
                    footSource="rag_search",
                    footType="document",
                )
            )

            # 更新偏移量，因为脚注被移除会导致后续内容前移
            offset += len(match.group(0))

    # 最后统一移除所有脚注
    task.runtime.answer = foot_note_pattern.sub("", task.runtime.answer).strip()
    record_content = RecordContent(
        question=task.runtime.question,
        answer=task.runtime.answer,
        facts=task.runtime.facts,
        data={},
    )

    try:
        # 加密Record数据
        encrypt_data, encrypt_config = Security.encrypt(record_content.model_dump_json(by_alias=True))
    except Exception:
        logger.exception("[Scheduler] 问答对加密错误")
        return

    # 保存Flow信息
    if task.state:
        # 遍历查找数据，并添加
        await TaskManager.save_flow_context(task.id, task.context)

    # 整理Record数据
    current_time = round(datetime.now(UTC).timestamp(), 2)
    record = Record(
        id=task.ids.record_id,
        groupId=task.ids.group_id,
        conversationId=task.ids.conversation_id,
        taskId=task.id,
        user_sub=user_sub,
        content=encrypt_data,
        key=encrypt_config,
        metadata=RecordMetadata(
            timeCost=task.tokens.full_time,
            inputTokens=task.tokens.input_tokens,
            outputTokens=task.tokens.output_tokens,
            footNoteMetadataList=foot_note_metadata_list,
            feature={},
        ),
        createdAt=current_time,
        flow=[i["_id"] for i in task.context],
    )

    # 检查是否存在group_id
    if not await RecordManager.check_group_id(task.ids.group_id, user_sub):
        record_group = await RecordManager.create_record_group(
            task.ids.group_id, user_sub, post_body.conversation_id, task.id,
        )
        if not record_group:
            logger.error("[Scheduler] 创建问答组失败")
            return
    else:
        record_group = task.ids.group_id

    # 修改文件状态
    await DocumentManager.change_doc_status(user_sub, post_body.conversation_id, record_group)
    # 保存Record
    await RecordManager.insert_record_data_into_record_group(user_sub, record_group, record)
    # 保存与答案关联的文件
    await DocumentManager.save_answer_doc(user_sub, record_group, used_docs)

    if post_body.app and post_body.app.app_id:
        # 更新最近使用的应用
        await AppCenterManager.update_recent_app(user_sub, post_body.app.app_id)

    # 若状态为成功，删除Task
    if not task.state or task.state.status == StepStatus.SUCCESS:
        await TaskManager.delete_task_by_task_id(task.id)
    else:
        # 更新Task
        await TaskManager.save_task(task.id, task)
