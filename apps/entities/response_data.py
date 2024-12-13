# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ResponseData(BaseModel):
    code: int
    message: str
    result: dict


class ConversationData(BaseModel):
    conversation_id: str
    title: str
    created_time: datetime


class ConversationListData(BaseModel):
    code: int
    message: str
    result: list[ConversationData]


class RecordData(BaseModel):
    conversation_id: str
    record_id: str
    question: str
    answer: str
    is_like: Optional[int] = None
    created_time: datetime
    group_id: str


class RecordListData(BaseModel):
    code: int
    message: str
    result: list[RecordData]


class RecordQueryData(BaseModel):
    conversation_id: str
    record_id: str
    encrypted_question: str
    question_encryption_config: dict
    encrypted_answer: str
    answer_encryption_config: dict
    created_time: str
    is_like: Optional[int] = None
    group_id: str
