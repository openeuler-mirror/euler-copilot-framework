"""上下文管理

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from apps.common.security import Security
from apps.entities.collection import RecordContent
from apps.entities.request_data import RequestData
from apps.llm.patterns.facts import Facts
from apps.manager import RecordManager, TaskManager


async def get_context(user_sub: str, post_body: RequestData, n: int) -> tuple[list[dict[str, str]], list[str]]:
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
    messages = []
    for record in records:
        record_data = RecordContent.model_validate_json(Security.decrypt(record.data, record.key))

        messages = [
            {"role": "user", "content": record_data.question},
            {"role": "assistant", "content": record_data.answer},
            *messages,
        ]

    return messages, facts


async def generate_facts(task_id: str, question: str) -> list[str]:
    """生成Facts"""
    task = await TaskManager.get_task(task_id)
    if not task:
        err = "Task not found"
        raise ValueError(err)

    message = {
        "question": question,
        "answer": task.record.content.answer,
    }

    return await Facts().generate(task_id, message=message)
