# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from typing import Union

from fastapi import APIRouter, Depends, Query, status

from apps.common.security import Security
from apps.dependency.user import verify_user, get_user
from apps.entities.response_data import RecordData, RecordListData, ResponseData
from apps.entities.user import User
from apps.manager.record import RecordManager
from apps.manager.conversation import ConversationManager

router = APIRouter(
    prefix="/api/record",
    tags=["record"],
    dependencies=[
        Depends(verify_user)
    ]
)


@router.get("", response_model=Union[RecordListData, ResponseData])
async def get_record(
        user: User = Depends(get_user),
        conversation_id: str = Query(min_length=1, max_length=100)
):
    cur_conv = ConversationManager.get_conversation_by_conversation_id(
        conversation_id)
    if not cur_conv or cur_conv.user_sub != user.user_sub:
        return ResponseData(code=status.HTTP_204_NO_CONTENT, message="session_id not found", result={})
    record_list = RecordManager.query_encrypted_data_by_conversation_id(conversation_id, order="asc")
    result = []
    for item in record_list:
        question = Security.decrypt(
            item.encrypted_question, item.question_encryption_config)
        answer = Security.decrypt(
            item.encrypted_answer, item.answer_encryption_config)
        tmp_record = RecordData(
            conversation_id=item.conversation_id, record_id=item.record_id, question=question, answer=answer,
            created_time=item.created_time, is_like=item.is_like, group_id=item.group_id)
        result.append(tmp_record)
    return RecordListData(code=status.HTTP_200_OK, message="success", result=result)
