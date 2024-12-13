# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import logging
from datetime import datetime

import pytz
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from apps.constants import NEW_CHAT
from apps.dependency.csrf import verify_csrf_token
from apps.dependency.user import get_user, verify_user
from apps.entities.request_data import DeleteConversationData, ModifyConversationData
from apps.entities.response_data import ConversationData, ConversationListData, ResponseData
from apps.entities.user import User
from apps.manager.audit_log import AuditLogData, AuditLogManager
from apps.manager.conversation import ConversationManager
from apps.manager.record import RecordManager

router = APIRouter(
    prefix="/api/conversation",
    tags=["conversation"],
    dependencies=[
        Depends(verify_user)
    ]
)
logger = logging.getLogger('gunicorn.error')


@router.get("", response_model=ConversationListData)
async def get_conversation_list(user: User = Depends(get_user)):
    user_sub = user.user_sub
    conversations = ConversationManager.get_conversation_by_user_sub(user_sub)
    for conv in conversations:
        record_list = RecordManager.query_encrypted_data_by_conversation_id(conv.conversation_id)
        if not record_list:
            ConversationManager.update_conversation_metadata_by_conversation_id(
                conv.conversation_id,
                NEW_CHAT,
                datetime.now(pytz.timezone('Asia/Shanghai'))
            )
            break
    conversations = ConversationManager.get_conversation_by_user_sub(user_sub)
    result_conversations = []
    for conv in conversations:
        conv_data = ConversationData(
            conversation_id=conv.conversation_id, title=conv.title, created_time=conv.created_time)
        result_conversations.append(conv_data)
    return ConversationListData(code=status.HTTP_200_OK, message="success", result=result_conversations)


@router.post("", response_model=ResponseData, dependencies=[Depends(verify_csrf_token)])
async def add_conversation(user: User = Depends(get_user)):
    return await add_conversation_func(user)


@router.put("", response_model=ResponseData, dependencies=[Depends(verify_csrf_token)])
async def update_conversation(
    post_body: ModifyConversationData,
    user: User = Depends(get_user),
    conversation_id: str = Query(min_length=1, max_length=100)
):
    cur_conv = ConversationManager.get_conversation_by_conversation_id(
        conversation_id)
    if not cur_conv or cur_conv.user_sub != user.user_sub:
        logger.error("Conversation: conversation_id not found.")
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)
    conv = ConversationManager.update_conversation_by_conversation_id(
        conversation_id, post_body.title)
    converse_result = ConversationData(
        conversation_id=conv.conversation_id, title=conv.title, created_time=conv.created_time)
    return ResponseData(code=status.HTTP_200_OK, message="success", result={
        "conversation": converse_result
    })


@router.post("/delete", response_model=ResponseData, dependencies=[Depends(verify_csrf_token)])
async def delete_conversation(request: Request, post_body: DeleteConversationData, user: User = Depends(get_user)):
    deleted_conversation = []
    for conversation_id in post_body.conversation_list:
        cur_conv = ConversationManager.get_conversation_by_conversation_id(
            conversation_id)
        # Session有误，跳过
        if not cur_conv or cur_conv.user_sub != user.user_sub:
            continue

        try:
            RecordManager.delete_encrypted_qa_pair_by_conversation_id(conversation_id)
            ConversationManager.delete_conversation_by_conversation_id(conversation_id)
            data = AuditLogData(method_type='post', source_name='/conversation/delete', ip=request.client.host,
                                result=f'deleted conversation with id: {conversation_id}', reason='')
            AuditLogManager.add_audit_log(user.user_sub, data)
            deleted_conversation.append(conversation_id)
        except Exception as e:
            # 删除过程中发生错误，跳过
            logger.error(f"删除Conversation错误：{conversation_id}, {str(e)}")
            continue
    return ResponseData(code=status.HTTP_200_OK, message="success", result={
        "conversation_id_list": deleted_conversation
    })


async def add_conversation_func(user: User):
    user_sub = user.user_sub
    conversations = ConversationManager.get_conversation_by_user_sub(user_sub)
    for conv in conversations:
        record_list = RecordManager.query_encrypted_data_by_conversation_id(conv.conversation_id)
        if not record_list:
            ConversationManager.update_conversation_metadata_by_conversation_id(
                conv.conversation_id,
                NEW_CHAT,
                datetime.now(pytz.timezone('Asia/Shanghai'))
            )
            return ResponseData(
                code=status.HTTP_200_OK,
                message="success",
                result={
                    "conversation_id": conv.conversation_id
                }
            )
    conversation_id = ConversationManager.add_conversation_by_user_sub(
        user_sub)
    if not conversation_id:
        return ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="generate conversation_id fail", result={})
    return ResponseData(code=status.HTTP_200_OK, message="success", result={
        "conversation_id": conversation_id
    })
