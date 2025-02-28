"""上下文管理

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import logging
from datetime import datetime, timezone
from typing import Union

import ray

from apps.common.security import Security
from apps.entities.collection import Document, Record, RecordContent
from apps.entities.record import RecordDocument
from apps.entities.request_data import RequestData
from apps.entities.task import TaskBlock
from apps.llm.patterns.facts import Facts
from apps.manager.document import DocumentManager
from apps.manager.record import RecordManager
from apps.manager.task import TaskManager

logger = logging.getLogger("ray")


async def get_docs(user_sub: str, post_body: RequestData) -> tuple[Union[list[RecordDocument], list[Document]], list[str]]:
    """获取当前问答可供关联的文档"""
    doc_ids = []
    if post_body.group_id:
        # 是重新生成，直接从RecordGroup中获取
        docs = await DocumentManager.get_used_docs_by_record_group(user_sub, post_body.group_id)
        doc_ids += [doc.id for doc in docs]
    else:
        # 是新提问
        # 从Conversation中获取刚上传的文档
        docs = await DocumentManager.get_unused_docs(user_sub, post_body.conversation_id)
        # 从最近10条Record中获取文档
        docs += await DocumentManager.get_used_docs(user_sub, post_body.conversation_id, 10)
        doc_ids += [doc.id for doc in docs]

    return docs, doc_ids


async def get_context(user_sub: str, post_body: RequestData, n: int) -> tuple[str, list[str]]:
    """获取当前问答的上下文信息

    注意：这里的n要比用户选择的多，因为要考虑事实信息和历史问题
    """
    # 最多15轮
    n = min(n, 15)

    # 获取最后n+5条Record
    records = await RecordManager.query_record_by_conversation_id(user_sub, post_body.conversation_id, n + 5)
    # 获取事实信息
    facts = []
    for record in records:
        facts.extend(record.facts)

    # 组装问答
    messages = "<conversation>"
    for record in records:
        record_data = RecordContent.model_validate_json(Security.decrypt(record.data, record.key))

        messages += f"""
            <user>
                {record_data.question}
            </user>
            <assistant>
                {record_data.answer}
            </assistant>
        """
    messages += "</conversation>"

    return messages, facts


async def generate_facts(task: TaskBlock, question: str) -> list[str]:
    """生成Facts"""
    message = {
        "question": question,
        "answer": task.record.content.answer,
    }

    return await Facts().generate(task.record.task_id, message=message)


async def save_data(task_id: str, user_sub: str, post_body: RequestData, used_docs: list[str]) -> None:
    """保存当前Executor、Task、Record等的数据"""
    # 获取当前Task
    task_actor = ray.get_actor("task")
    task: TaskBlock = await task_actor.get_task.remote(task_id)
    # 加密Record数据
    try:
        encrypt_data, encrypt_config = Security.encrypt(task.record.content.model_dump_json(by_alias=True))
    except Exception:
        logger.exception("[Scheduler] 问答对加密错误")
        return

    # 保存Flow信息
    if task.flow_state:
        # 循环创建FlowHistory
        history_data = []
        # 遍历查找数据，并添加
        for history_id in task.new_context:
            for history in task.flow_context.values():
                if history.id == history_id:
                    history_data.append(history)
                    break
        await TaskManager.create_flows(history_data)

        # 修改metadata里面时间为实际运行时间
        task.record.metadata.time_cost = round(datetime.now(timezone.utc).timestamp() - task.record.metadata.time_cost, 2)

    # 提取facts
    # 记忆提取
    facts = await generate_facts(task, post_body.question)

    # 整理Record数据
    record = Record(
        record_id=task.record.id,
        user_sub=user_sub,
        data=encrypt_data,
        key=encrypt_config,
        facts=facts,
        metadata=task.record.metadata,
        created_at=task.record.created_at,
        flow=task.new_context,
    )

    record_group = task.record.group_id
    # 检查是否存在group_id
    if not await RecordManager.check_group_id(record_group, user_sub):
        record_group = await RecordManager.create_record_group(user_sub, post_body.conversation_id, task.record.task_id)
        if not record_group:
            logger.error("[Scheduler] 创建问答组失败")
            return

    # 修改文件状态
    await DocumentManager.change_doc_status(user_sub, post_body.conversation_id, record_group)
    # 保存Record
    await RecordManager.insert_record_data_into_record_group(user_sub, record_group, record)
    # 保存与答案关联的文件
    await DocumentManager.save_answer_doc(user_sub, record_group, used_docs)

    # 保存Task
    await task_actor.save_task.remote(task_id)
