# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import json

from fastapi import APIRouter, Depends, status, HTTPException
import logging

from apps.dependency.user import verify_user, get_user
from apps.dependency.csrf import verify_csrf_token
from apps.entities.request_data import AddCommentData
from apps.entities.response_data import ResponseData
from apps.entities.user import User
from apps.manager.comment import CommentData, CommentManager
from apps.manager.record import RecordManager
from apps.manager.conversation import ConversationManager


router = APIRouter(
    prefix="/api/comment",
    tags=["comment"],
    dependencies=[
        Depends(verify_user)
    ]
)
logger = logging.getLogger('gunicorn.error')


@router.post("", response_model=ResponseData, dependencies=[Depends(verify_csrf_token)])
async def add_comment(post_body: AddCommentData, user: User = Depends(get_user)):
    user_sub = user.user_sub
    cur_record = RecordManager.query_encrypted_data_by_record_id(
        post_body.record_id)
    if not cur_record:
        logger.error("Comment: record_id not found.")
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)
    cur_conv = ConversationManager.get_conversation_by_conversation_id(
        cur_record.conversation_id)
    if not cur_conv or cur_conv.user_sub != user.user_sub:
        logger.error("Comment: conversation_id not found.")
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)
    cur_comment = CommentManager.query_comment(post_body.record_id)
    comment_data = CommentData(post_body.record_id, post_body.is_like, post_body.dislike_reason,
                               post_body.reason_link, post_body.reason_description)
    if cur_comment:
        CommentManager.update_comment(user_sub, comment_data)
    else:
        CommentManager.add_comment(user_sub, comment_data)
    return ResponseData(code=status.HTTP_200_OK, message="success", result={})
