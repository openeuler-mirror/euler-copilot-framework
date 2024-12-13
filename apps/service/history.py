# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from __future__ import annotations

from typing import List, Dict
import uuid

from apps.manager.record import RecordManager
from apps.common.security import Security
from apps.manager.conversation import ConversationManager


class History:
    """
    获取对话历史记录
    """
    def __init__(self):
        raise NotImplementedError("History类无法被实例化！")

    @staticmethod
    def get_latest_records(conversation_id: str, record_id: str | None = None, n: int = 1):
        # 是重新生成，从record_id中拿出group_id
        if record_id is not None:
            record = RecordManager().query_encrypted_data_by_record_id(record_id)
            group_id = record.group_id
        # 全新生成，创建新的group_id
        else:
            group_id = str(uuid.uuid4().hex)

        record_list = RecordManager().query_encrypted_data_by_conversation_id(
            conversation_id, n, group_id)
        record_list_sorted = sorted(record_list, key=lambda x: x.created_time)

        return group_id, record_list_sorted

    @staticmethod
    def get_history_messages(conversation_id, record_id):
        group_id, record_list_sorted = History.get_latest_records(conversation_id, record_id)
        history: List[Dict[str, str]] = []
        for item in record_list_sorted:
            tmp_question = Security.decrypt(
                item.encrypted_question, item.question_encryption_config)
            tmp_answer = Security.decrypt(
                item.encrypted_answer, item.answer_encryption_config)
            history.append({"role": "user", "content": tmp_question})
            history.append({"role": "assistant", "content": tmp_answer})
        return group_id, history

    @staticmethod
    def get_summary(conversation_id):
        """
        根据对话ID，从数据库中获取对话的总结
        :param conversation_id: 对话ID
        :return: 对话总结信息，字符串或None
        """
        conv = ConversationManager.get_conversation_by_conversation_id(conversation_id)
        if conv.summary is None:
            return ""
        return conv.summary
