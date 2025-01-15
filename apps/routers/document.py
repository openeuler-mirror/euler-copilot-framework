"""FastAPI文件上传路由

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import JSONResponse

from apps.dependency import get_user, verify_csrf_token, verify_user
from apps.entities.enum import DocumentStatus
from apps.entities.response_data import (
    ConversationDocumentItem,
    ConversationDocumentMsg,
    ConversationDocumentRsp,
    ResponseData,
    UploadDocumentMsg,
    UploadDocumentMsgItem,
    UploadDocumentRsp,
)
from apps.manager.document import DocumentManager
from apps.service.knowledge_base import KnowledgeBaseService

router = APIRouter(
    prefix="/api/document",
    tags=["document"],
    dependencies=[
        Depends(verify_user),
    ],
)


@router.post("/{conversation_id}", dependencies=[Depends(verify_csrf_token)])
async def document_upload(  # noqa: ANN201
    conversation_id: str, documents: Annotated[list[UploadFile], File(...)], user_sub: Annotated[str, Depends(get_user)],
):
    """上传文档"""
    result = await DocumentManager.storage_docs(user_sub, conversation_id, documents)
    await KnowledgeBaseService.send_file_to_rag(result)

    # 返回所有Framework已知的文档
    succeed_document: list[UploadDocumentMsgItem] = [
        UploadDocumentMsgItem(
            _id=doc.id,
            name=doc.name,
            type=doc.type,
            size=doc.size,
        ) for doc in result
    ]

    return JSONResponse(status_code=200, content=UploadDocumentRsp(
        code=status.HTTP_200_OK,
        message="上传成功",
        result=UploadDocumentMsg(documents=succeed_document),
    ).model_dump(exclude_none=True, by_alias=False))


@router.get("/{conversation_id}", response_model=ConversationDocumentRsp)
async def get_document_list(  # noqa: ANN201
    conversation_id: str, user_sub: Annotated[str, Depends(get_user)], used: Annotated[bool, Query()] = False, unused: Annotated[bool, Query()] = True,  # noqa: FBT002
):
    """获取文档列表"""
    result = []
    if used:
        # 拿到所有已使用的文档
        docs = await DocumentManager.get_used_docs(user_sub, conversation_id)
        result += [
            ConversationDocumentItem(
                _id=item.id,
                name=item.name,
                type=item.type,
                size=round(item.size, 2),
                status=DocumentStatus.USED,
                created_at=item.created_at,
            ) for item in docs
        ]

    if unused:
        # 拿到所有未使用的文档
        unused_docs = await DocumentManager.get_unused_docs(user_sub, conversation_id)
        doc_status = await KnowledgeBaseService.get_doc_status_from_rag([item.id for item in unused_docs])
        for current_doc in unused_docs:
            for status_item in doc_status:
                if current_doc.id != status_item.id:
                    continue

                if status_item.status == "success":
                    new_status = DocumentStatus.UNUSED
                elif status_item.status == "failed":
                    new_status = DocumentStatus.FAILED
                else:
                    new_status = DocumentStatus.PROCESSING

                result += [
                    ConversationDocumentItem(
                        _id=current_doc.id,
                        name=current_doc.name,
                        type=current_doc.type,
                        size=round(current_doc.size, 2),
                        status=new_status,
                        created_at=current_doc.created_at,
                    ),
                ]

    # 对外展示的时候用id，不用alias
    return JSONResponse(status_code=status.HTTP_200_OK, content=ConversationDocumentRsp(
        code=status.HTTP_200_OK,
        message="获取成功",
        result=ConversationDocumentMsg(documents=result),
    ).model_dump(exclude_none=True, by_alias=False))


@router.delete("/{document_id}", response_model=ResponseData)
async def delete_single_document(document_id: str, user_sub: Annotated[str, Depends(get_user)]):  # noqa: ANN201
    """删除单个文件"""
    # 在Framework侧删除
    result = await DocumentManager.delete_document(user_sub, [document_id])
    if not result:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="删除文件失败",
            result={},
        ).model_dump(exclude_none=True, by_alias=False))
    # 在RAG侧删除
    result = await KnowledgeBaseService.delete_doc_from_rag([document_id])
    if not result:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="RAG端删除文件失败",
            result={},
        ).model_dump(exclude_none=True, by_alias=False))

    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="删除成功",
        result={},
    ).model_dump(exclude_none=True, by_alias=False))
