# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI：对话相关接口"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from apps.dependency import verify_personal_token, verify_session
from apps.schemas.conversation import (
    ChangeConversationData,
    ConversationListItem,
    ConversationListMsg,
    ConversationListRsp,
    DeleteConversationData,
    DeleteConversationMsg,
    DeleteConversationRsp,
    UpdateConversationRsp,
)
from apps.schemas.response_data import ResponseData
from apps.services.conversation import ConversationManager
from apps.services.document import DocumentManager

router = APIRouter(
    prefix="/api/conversation",
    tags=["conversation"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)
_logger = logging.getLogger(__name__)


@router.get("", response_model=ConversationListRsp, responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ResponseData},
    },
)
async def get_conversation_list(request: Request) -> JSONResponse:
    """GET /conversation: 获取对话列表"""
    conversations = await ConversationManager.get_conversation_by_user(
        request.state.user_id,
    )
    # 把已有对话转换为列表
    result_conversations = []
    for conv in conversations:
        conversation_list_item = ConversationListItem(
            conversationId=conv.id,
            title=conv.title,
            docCount=await DocumentManager.get_doc_count(conv.id),
            createdTime=conv.createdAt.strftime("%Y-%m-%d %H:%M:%S"),
            appId=conv.appId,
            debug=conv.isTemporary,
        )
        result_conversations.append(conversation_list_item)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ConversationListRsp(
                code=status.HTTP_200_OK,
                message="success",
                result=ConversationListMsg(conversations=result_conversations),
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@router.post("", response_model=UpdateConversationRsp)
async def update_conversation(
    request: Request,
    conversation_id: Annotated[uuid.UUID, Query(alias="conversationId")],
    post_body: ChangeConversationData,
) -> JSONResponse:
    """PUT /conversation: 更新特定Conversation的信息"""
    # 判断Conversation是否合法
    conv = await ConversationManager.get_conversation_by_conversation_id(request.state.user_id, conversation_id)
    if not conv or conv.userId != request.state.user_id:
        _logger.error("[Conversation] conversation_id 不存在")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="conversation_id not found",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )

    # 更新Conversation数据
    try:
        await ConversationManager.update_conversation_by_conversation_id(
            request.state.user_id,
            conversation_id,
            {
                "title": post_body.title,
            },
        )
    except Exception:
        _logger.exception("[Conversation] 更新对话数据失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="update conversation failed",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            UpdateConversationRsp(
                code=status.HTTP_200_OK,
                message="success",
                result=ConversationListItem(
                    conversationId=conv.id,
                    title=conv.title,
                    docCount=await DocumentManager.get_doc_count(conv.id),
                    createdTime=conv.createdAt.strftime("%Y-%m-%d %H:%M:%S"),
                    appId=conv.appId,
                    debug=conv.isTemporary,
                ),
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@router.delete("", response_model=ResponseData)
async def delete_conversation(
    request: Request,
    post_body: DeleteConversationData,
) -> JSONResponse:
    """DELETE /conversation: 删除特定对话"""
    deleted_conversation = []
    for conversation_id in post_body.conversation_list:
        # 删除对话
        await ConversationManager.delete_conversation_by_conversation_id(
            request.state.user_id,
            conversation_id,
        )
        # 删除对话对应的文件
        auth_header = getattr(request.session, "session_id", None) or request.state.personal_token
        await DocumentManager.delete_document_by_conversation_id(
            conversation_id,
            auth_header,
        )
        deleted_conversation.append(conversation_id)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            DeleteConversationRsp(
                code=status.HTTP_200_OK,
                message="success",
                result=DeleteConversationMsg(conversationIdList=deleted_conversation),
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )
