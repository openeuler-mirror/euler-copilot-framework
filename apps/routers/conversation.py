"""FastAPI：对话相关接口

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from datetime import datetime
from typing import Annotated, Optional

import pytz
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse

from apps.constants import LOGGER
from apps.dependency import get_user, verify_csrf_token, verify_user
from apps.entities.collection import Audit, Conversation
from apps.entities.request_data import (
    DeleteConversationData,
    ModifyConversationData,
)
from apps.entities.response_data import (
    AddConversationMsg,
    AddConversationRsp,
    ConversationListItem,
    ConversationListMsg,
    ConversationListRsp,
    ResponseData,
    UpdateConversationRsp,
)
from apps.manager import (
    AuditLogManager,
    ConversationManager,
    DocumentManager,
    RecordManager,
)

router = APIRouter(
    prefix="/api/conversation",
    tags=["conversation"],
    dependencies=[
        Depends(verify_user),
    ],
)


async def create_new_conversation(user_sub: str, conv_list: list[Conversation]) -> Optional[Conversation]:
    """判断并创建新对话"""
    create_new = False
    if not conv_list:
        create_new = True
    else:
        last_conv = conv_list[-1]
        conv_records = await RecordManager.query_record_by_conversation_id(user_sub, last_conv.id, 1, "desc")
        if len(conv_records) > 0:
            create_new = True

    # 新建对话
    if create_new:
        new_conv = await ConversationManager.add_conversation_by_user_sub(user_sub)
        if not new_conv:
            err = "Create new conversation failed."
            raise RuntimeError(err)
        return new_conv
    return None


@router.get("", response_model=ConversationListRsp, responses={
    status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ResponseData},
})
async def get_conversation_list(user_sub: Annotated[str, Depends(get_user)]):  # noqa: ANN201
    """获取对话列表"""
    conversations = await ConversationManager.get_conversation_by_user_sub(user_sub)
    # 把已有对话转换为列表
    result_conversations = [
        ConversationListItem(
            conversation_id=conv.id,
            title=conv.title,
            doc_count=await DocumentManager.get_doc_count(user_sub, conv.id),
            created_time=datetime.fromtimestamp(conv.created_at, tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S"),
        ) for conv in conversations
    ]

    # 新建对话
    try:
        new_conv = await create_new_conversation(user_sub, conversations)
    except RuntimeError as e:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={
            "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": str(e),
            "result": {},
        })

    if new_conv:
        result_conversations.append(ConversationListItem(
            conversation_id=new_conv.id,
            title=new_conv.title,
            doc_count=0,
            created_time=datetime.fromtimestamp(new_conv.created_at, tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S"),
        ))

    return JSONResponse(status_code=status.HTTP_200_OK,
        content=ConversationListRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=ConversationListMsg(conversations=result_conversations),
        ).model_dump(exclude_none=True, by_alias=True),
    )



@router.post("", dependencies=[Depends(verify_csrf_token)], response_model=AddConversationRsp)
async def add_conversation(user_sub: Annotated[str, Depends(get_user)]):  # noqa: ANN201
    """手动创建新对话"""
    conversations = await ConversationManager.get_conversation_by_user_sub(user_sub)
    # 尝试创建新对话
    try:
        new_conv = await create_new_conversation(user_sub, conversations)
    except RuntimeError as e:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=str(e),
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    if not new_conv:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=ResponseData(
            code=status.HTTP_409_CONFLICT,
            message="No need to create new conversation.",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))

    return JSONResponse(status_code=status.HTTP_200_OK, content=AddConversationRsp(
        code=status.HTTP_200_OK,
        message="success",
        result=AddConversationMsg(conversation_id=new_conv.id),
    ).model_dump(exclude_none=True, by_alias=True))


@router.put("", response_model=UpdateConversationRsp, dependencies=[Depends(verify_csrf_token)])
async def update_conversation(  # noqa: ANN201
    post_body: ModifyConversationData,
    conversation_id: Annotated[str, Query()],
    user_sub: Annotated[str, Depends(get_user)],
):
    """更新特定Conversation的数据"""
    # 判断Conversation是否合法
    conv = await ConversationManager.get_conversation_by_conversation_id(user_sub, conversation_id)
    if not conv or conv.user_sub != user_sub:
        LOGGER.error("Conversation: conversation_id not found.")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=ResponseData(
            code=status.HTTP_400_BAD_REQUEST,
            message="conversation_id not found",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))

    # 更新Conversation数据
    change_status = await ConversationManager.update_conversation_by_conversation_id(
        user_sub,
        conversation_id,
        {
            "title": post_body.title,
        },
    )

    if not change_status:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="update conversation failed",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))

    return JSONResponse(status_code=status.HTTP_200_OK,
        content=UpdateConversationRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=ConversationListItem(
                conversation_id=conv.id,
                title=conv.title,
                doc_count=await DocumentManager.get_doc_count(user_sub, conv.id),
                created_time=datetime.fromtimestamp(conv.created_at, tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S"),
            ),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.delete("", response_model=ResponseData, dependencies=[Depends(verify_csrf_token)])
async def delete_conversation(request: Request, post_body: DeleteConversationData, user_sub: Annotated[str, Depends(get_user)]):  # noqa: ANN201
    """删除特定对话"""
    deleted_conversation = []
    for conversation_id in post_body.conversation_list:
        # 删除对话
        result = await ConversationManager.delete_conversation_by_conversation_id(user_sub, conversation_id)
        if not result:
            continue

        # 删除对话对应的文件
        await DocumentManager.delete_document_by_conversation_id(user_sub, conversation_id)

        # 添加审计日志
        request_host = None
        if request.client is not None:
            request_host = request.client.host
        data = Audit(
            user_sub=user_sub,
            http_method="delete",
            module="/conversation",
            client_ip=request_host,
            message=f"deleted conversation with id: {conversation_id}",
        )
        await AuditLogManager.add_audit_log(data)

        deleted_conversation.append(conversation_id)

    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="success",
        result={"conversation_id_list": deleted_conversation},
    ).model_dump(exclude_none=True, by_alias=True))
