"""
FastAPI文件上传路由

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status, HTTPException
from fastapi.responses import JSONResponse

from apps.dependency import get_session, get_user, verify_user
from apps.schemas.enum_var import DocumentStatus
from apps.schemas.response_data import (
    ConversationDocumentItem,
    ConversationDocumentMsg,
    ConversationDocumentRsp,
    ResponseData,
    UploadDocumentMsg,
    UploadDocumentMsgItem,
    UploadDocumentRsp,
)
from apps.services.document import DocumentManager
from apps.services.knowledge_base import KnowledgeBaseService
from apps.scheduler.variable.type import VariableType

router = APIRouter(
    prefix="/api/document",
    tags=["document"],
    dependencies=[
        Depends(verify_user),
    ],
)


@router.post("/{conversation_id}")
async def document_upload(  # noqa: ANN201
    conversation_id: str,
    documents: Annotated[list[UploadFile], File(...)],
    user_sub: Annotated[str, Depends(get_user)],
    session_id: Annotated[str, Depends(get_session)],
    scope: str = "system",
    var_name: Optional[str] = None,
    var_type: Optional[str] = None,
    flow_id: Optional[str] = None,
):
    """上传文档 - 支持system和conversation scope
    
    🔑 优化说明：支持前端两阶段处理逻辑
    - 前端第一阶段：已清空file_id/file_ids但保留配置
    - 前端第二阶段：上传文件，后端只更新file_id/file_ids
    """
    # 参数验证
    if scope == "conversation":
        if not var_name or not var_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="对于conversation scope，必须提供var_name和var_type参数"
            )
        
        # 验证var_type必须是FILE或ARRAY_FILE
        if var_type not in [VariableType.FILE.value, VariableType.ARRAY_FILE.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"var_type必须是'{VariableType.FILE.value}'或'{VariableType.ARRAY_FILE.value}'"
            )

        # 🔑 重要：验证文件上传前，变量必须已存在（前端第一阶段已创建）
        is_valid, error_msg = await DocumentManager.validate_file_upload_for_variable(
            user_sub, documents, var_name, var_type, scope, conversation_id, flow_id
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件上传验证失败: {error_msg}"
            )

    elif scope != "system":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此接口只支持system和conversation scope，请使用对应的专用接口"
        )
    
    try:
        # 🔑 第一步：上传文件到MinIO和MongoDB
        result = await DocumentManager.storage_docs(user_sub, conversation_id, documents, scope, var_name, var_type)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="文件上传失败：没有成功上传任何文件"
            )
        
        # 🔑 第二步：只有system scope需要向量化（conversation scope的文件由业务逻辑决定是否向量化）
        if scope == "system":
            await KnowledgeBaseService.send_file_to_rag(session_id, result)

        # 🔑 成功响应：返回所有Framework已知的文档
        succeed_document: list[UploadDocumentMsgItem] = [
            UploadDocumentMsgItem(
                _id=doc.id,
                name=doc.name,
                type=doc.type,
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
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        # 🔑 处理其他异常，提供更详细的错误信息
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"文档上传失败: conversation_id={conversation_id}, scope={scope}, var_name={var_name}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档上传失败: {str(e)}"
        )


@router.post("/user")
async def document_upload_user(  # noqa: ANN201
    documents: Annotated[list[UploadFile], File(...)],
    user_sub: Annotated[str, Depends(get_user)],
    session_id: Annotated[str, Depends(get_session)],
    var_name: str,
    var_type: str,
):
    """用户scope文档上传"""
    # 验证var_type必须是FILE或ARRAY_FILE
    if var_type not in [VariableType.FILE.value, VariableType.ARRAY_FILE.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"var_type必须是'{VariableType.FILE.value}'或'{VariableType.ARRAY_FILE.value}'"
        )
    
    # 文件上传前验证
    is_valid, error_msg = await DocumentManager.validate_file_upload_for_variable(
        user_sub, documents, var_name, var_type, "user"
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件上传验证失败: {error_msg}"
        )
    
    result = await DocumentManager.storage_docs_user(user_sub, documents, var_name, var_type)
    await KnowledgeBaseService.send_file_to_rag(session_id, result)

    # 返回所有Framework已知的文档
    succeed_document: list[UploadDocumentMsgItem] = [
        UploadDocumentMsgItem(
            _id=doc.id,
            name=doc.name,
            type=doc.type,
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


@router.post("/env/{flow_id}")
async def document_upload_env(  # noqa: ANN201
    flow_id: str,
    documents: Annotated[list[UploadFile], File(...)],
    user_sub: Annotated[str, Depends(get_user)],
    session_id: Annotated[str, Depends(get_session)],
):
    """环境scope文档上传"""
    # 文件上传前验证
    is_valid, error_msg = await DocumentManager.validate_file_upload_for_variable(
        user_sub, documents, "env.files", "array[file]", "env", flow_id=flow_id
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件上传验证失败: {error_msg}"
        )
    
    result = await DocumentManager.storage_docs_env(user_sub, flow_id, documents)
    await KnowledgeBaseService.send_file_to_rag(session_id, result)





@router.get("/{conversation_id}", response_model=ConversationDocumentRsp)
async def get_document_list(  # noqa: ANN201
    conversation_id: str,
    user_sub: Annotated[str, Depends(get_user)],
    session_id: Annotated[str, Depends(get_session)],
    *,
    used: Annotated[bool, Query()] = False,
    unused: Annotated[bool, Query()] = True,
):
    """获取文档列表"""
    result = []
    if used:
        # 拿到所有已使用的文档
        docs = await DocumentManager.get_used_docs(user_sub, conversation_id, type="question")
        result += [
            ConversationDocumentItem(
                _id=item.id,
                name=item.name,
                type=item.type,
                size=round(item.size, 2),
                status=DocumentStatus.USED,
                created_at=item.created_at,
            )
            for item in docs
        ]

    if unused:
        # 拿到所有未使用的文档
        unused_docs = await DocumentManager.get_unused_docs(user_sub, conversation_id)
        doc_status = await KnowledgeBaseService.get_doc_status_from_rag(session_id, [item.id for item in unused_docs])
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
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ConversationDocumentRsp(
            code=status.HTTP_200_OK,
            message="获取成功",
            result=ConversationDocumentMsg(documents=result),
        ).model_dump(exclude_none=True, by_alias=False),
    )


@router.delete("/{document_id}", response_model=ResponseData)
async def delete_single_document(  # noqa: ANN201
    document_id: str,
    user_sub: Annotated[str, Depends(get_user)],
    session_id: Annotated[str, Depends(get_session)],
):
    """删除单个文件"""
    # 在Framework侧删除
    result = await DocumentManager.delete_document(user_sub, [document_id])
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
    result = await KnowledgeBaseService.delete_doc_from_rag(session_id, [document_id])
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
