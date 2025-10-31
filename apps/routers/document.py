# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI文件上传路由"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, UploadFile, status
from fastapi.responses import JSONResponse

from apps.dependency import verify_personal_token, verify_session
from apps.schemas.document import (
    BaseDocumentItem,
    ConversationDocumentItem,
    ConversationDocumentMsg,
    ConversationDocumentRsp,
    UploadDocumentMsg,
    UploadDocumentRsp,
)
from apps.schemas.enum_var import DocumentStatus
from apps.schemas.response_data import ResponseData
from apps.services.conversation import ConversationManager
from apps.services.document import DocumentManager
from apps.services.knowledge_service import KnowledgeBaseService
from apps.services.user import UserManager

_logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/document",
    tags=["document"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)


@router.post("/{conversation_id}")
async def document_upload(
    request: Request,
    conversation_id: Annotated[uuid.UUID, Path()],
    documents: list[UploadFile],
) -> JSONResponse:
    """POST /document/{conversation_id}: 上传文档到指定对话"""
    result = await DocumentManager.storage_docs(request.state.user_id, conversation_id, documents)
    auth_header = getattr(request.session, "session_id", None) or request.state.personal_token
    await KnowledgeBaseService.send_file_to_rag(auth_header, result)

    # 返回所有Framework已知的文档
    succeed_document: list[BaseDocumentItem] = [
        BaseDocumentItem(
            id=doc.id,
            name=doc.name,
            type=doc.extension,
            size=doc.size,
        )
        for doc in result
    ]

    return JSONResponse(
        status_code=200,
        content=UploadDocumentRsp(
            code=status.HTTP_200_OK,
            message="上传成功",
            result=UploadDocumentMsg(documents=succeed_document),
        ).model_dump(exclude_none=True, by_alias=False),
    )


async def _get_user_name_or_skip(user_id: str, document_id: uuid.UUID) -> str | None:
    """获取用户名，如果用户不存在则记录警告并返回None"""
    user = await UserManager.get_user(user_id)
    if user is None:
        _logger.warning(
            "User not found for document %s (userId: %s), skipping document",
            document_id,
            user_id,
        )
        return None
    return user.userName


async def _process_used_documents(conversation_id: uuid.UUID) -> list[ConversationDocumentItem]:
    """处理已使用的文档列表"""
    result = []
    docs = await DocumentManager.get_used_docs(conversation_id)

    for item in docs:
        user_name = await _get_user_name_or_skip(item.userId, item.id)
        if user_name is None:
            continue

        result.append(
            ConversationDocumentItem(
                id=item.id,
                name=item.name,
                type=item.extension,
                size=round(item.size, 2),
                status=DocumentStatus.USED,
                created_at=item.createdAt,
                user_name=user_name,
            ),
        )

    return result


async def _process_unused_documents(
    conversation_id: uuid.UUID,
    auth_header: str,
) -> list[ConversationDocumentItem]:
    """处理未使用的文档列表"""
    result = []
    unused_docs = await DocumentManager.get_unused_docs(conversation_id)
    doc_status = await KnowledgeBaseService.get_doc_status_from_rag(
        auth_header, [item.id for item in unused_docs],
    )

    for current_doc in unused_docs:
        for status_item in doc_status:
            if current_doc.id != status_item.id:
                continue

            # 确定文档状态
            if status_item.status == "success":
                new_status = DocumentStatus.UNUSED
            elif status_item.status == "failed":
                new_status = DocumentStatus.FAILED
            else:
                new_status = DocumentStatus.PROCESSING

            # 获取用户名
            user_name = await _get_user_name_or_skip(current_doc.userId, current_doc.id)
            if user_name is None:
                continue

            result.append(
                ConversationDocumentItem(
                    id=current_doc.id,
                    name=current_doc.name,
                    type=current_doc.extension,
                    size=round(current_doc.size, 2),
                    status=new_status,
                    created_at=current_doc.createdAt,
                    user_name=user_name,
                ),
            )

    return result


@router.get("/{conversation_id}", response_model=ConversationDocumentRsp)
async def get_document_list(
    request: Request, conversation_id: Annotated[uuid.UUID, Path()],
    *,
    used: bool = False, unused: bool = True,
) -> JSONResponse:
    """GET /document/{conversation_id}: 获取特定对话的文档列表"""
    # 判断Conversation有权访问
    if not await ConversationManager.verify_conversation_access(request.state.user_id, conversation_id):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=ResponseData(
                code=status.HTTP_403_FORBIDDEN,
                message="无权限访问",
                result={},
            ),
        )

    result = []
    if used:
        result.extend(await _process_used_documents(conversation_id))

    if unused:
        auth_header = getattr(request.session, "session_id", None) or request.state.personal_token
        result.extend(await _process_unused_documents(conversation_id, auth_header))

    # 对外展示的时候用id，不用alias
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ConversationDocumentRsp(
            code=status.HTTP_200_OK,
            message="获取成功",
            result=ConversationDocumentMsg(documents=result),
        ).model_dump(exclude_none=True, by_alias=False),
    )


@router.delete("/{document_id}", response_model=ResponseData)
async def delete_single_document(
    request: Request, document_id: Annotated[str, Path()],
) -> JSONResponse:
    """DELETE /document/{document_id}: 删除单个文件"""
    # 在Framework侧删除
    result = await DocumentManager.delete_document(request.state.user_id, [document_id])
    if not result:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="删除文件失败",
                result={},
            ).model_dump(exclude_none=True, by_alias=False),
        )
    # 在RAG侧删除
    auth_header = getattr(request.session, "session_id", None) or request.state.personal_token
    result = await KnowledgeBaseService.delete_doc_from_rag(auth_header, [document_id])
    if not result:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="RAG端删除文件失败",
                result={},
            ).model_dump(exclude_none=True, by_alias=False),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="删除成功",
            result={},
        ).model_dump(exclude_none=True, by_alias=False),
    )
