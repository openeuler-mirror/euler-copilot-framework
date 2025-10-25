# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""文件Manager"""

import base64
import logging
import uuid

import asyncer
import magic
from fastapi import UploadFile
from sqlalchemy import and_, func, select

from apps.common.minio import MinioClient
from apps.common.postgres import postgres
from apps.models import (
    ConvDocAssociated,
    Conversation,
    ConversationDocument,
    Document,
    Record,
)

from .knowledge_service import KnowledgeBaseService
from .session import SessionManager

logger = logging.getLogger(__name__)


class DocumentManager:
    """文件相关操作"""

    @staticmethod
    def _storage_single_doc_minio(file_id: uuid.UUID, document: UploadFile) -> str:
        """存储单个文件到MinIO"""
        MinioClient.check_bucket("document")
        file = document.file
        # 获取文件MIME
        mime = magic.from_buffer(file.read(), mime=True)
        file.seek(0)

        # 上传到MinIO
        MinioClient.upload_file(
            bucket_name="document",
            object_name=str(file_id),
            data=file,
            content_type=mime,
            length=-1,
            part_size=10 * 1024 * 1024,
            metadata={
                "file_name": base64.b64encode(
                    document.filename.encode("utf-8"),
                ).decode("ascii") if document.filename else "",
            },
        )
        return mime

    @staticmethod
    async def storage_docs(
        user_id: str, conversation_id: uuid.UUID, documents: list[UploadFile],
    ) -> list[Document]:
        """存储多个文件"""
        uploaded_files = []

        for document in documents:
            if document.filename is None or document.size is None:
                logger.error("[DocumentManager] 文件名或大小为空: %s, %s", document.filename, document.size)
                continue

            file_id = uuid.uuid4()
            try:
                mime = await asyncer.asyncify(DocumentManager._storage_single_doc_minio)(file_id, document)
            except Exception:
                logger.exception("[DocumentManager] 上传文件失败")
                continue

            # 保存到数据库
            doc_info = Document(
                userId=user_id,
                name=document.filename,
                extension=mime,
                size=document.size / 1024.0,
                conversationId=conversation_id,
            )
            uploaded_files.append(doc_info)

        async with postgres.session() as session:
            session.add_all(uploaded_files)
            await session.commit()
        return uploaded_files


    @staticmethod
    async def get_unused_docs(conversation_id: uuid.UUID) -> list[Document]:
        """获取Conversation中未使用的文件"""
        async with postgres.session() as session:
            conv = (await session.scalars(
                select(ConversationDocument).where(
                    and_(
                        ConversationDocument.conversationId == conversation_id,
                        ConversationDocument.isUnused.is_(True),
                    ),
                ),
            )).all()
            if not conv:
                logger.error("[DocumentManager] 对话不存在: %s", conversation_id)
                return []

            docs_ids = [doc.documentId for doc in conv]
            docs = (await session.scalars(select(Document).where(Document.id.in_(docs_ids)))).all()
        return list(docs)


    @staticmethod
    async def get_used_docs_by_record(record_id: str, doc_type: str | None = None) -> list[Document]:
        """获取RecordGroup关联的文件"""
        if doc_type not in ["question", "answer", None]:
            logger.error("[DocumentManager] 参数错误: %s", doc_type)
            return []

        async with postgres.session() as session:
            record_docs = (await session.scalars(
                select(ConversationDocument).where(ConversationDocument.recordId == record_id),
            )).all()
            if not list(record_docs):
                logger.info("[DocumentManager] 记录组不存在: %s", record_id)
                return []

            doc_infos: list[Document] = []
            for doc in record_docs:
                doc_info = (await session.scalars(select(Document).where(Document.id == doc.documentId))).one_or_none()
                if doc_info:
                    doc_infos.append(doc_info)
        return doc_infos


    @staticmethod
    async def get_used_docs(
        conversation_id: uuid.UUID, record_num: int | None = 10, doc_type: str | None = None,
    ) -> list[Document]:
        """获取最后n次问答所用到的文件"""
        if doc_type not in ["question", "answer", None]:
            logger.error("[DocumentManager] 参数错误: %s", doc_type)
            return []

        async with postgres.session() as session:
            records = (await session.scalars(
                select(Record).where(
                    Record.conversationId == conversation_id,
                ).order_by(Record.createdAt.desc()).limit(record_num),
            )).all()

            docs = []
            for current_record in records:
                record_docs = (
                    await session.scalars(
                        select(ConversationDocument).where(ConversationDocument.recordId == current_record.id),
                    )
                ).all()
                if list(record_docs):
                    docs += [doc.documentId for doc in record_docs]

            # 去重
            docs = list(set(docs))
            result = []
            for doc_id in docs:
                doc = (await session.scalars(select(Document).where(Document.id == doc_id))).one_or_none()
                if doc:
                    result.append(doc)
        return result


    @staticmethod
    def _remove_doc_from_minio(doc_id: str) -> None:
        """从MinIO中删除文件"""
        MinioClient.delete_file("document", doc_id)


    @staticmethod
    async def delete_document(user_id: str, document_list: list[str]) -> None:
        """从未使用文件列表中删除一个文件"""
        async with postgres.session() as session:
            for doc in document_list:
                doc_info = await session.scalars(
                    select(Document).where(
                        and_(
                            Document.id == doc,
                            Document.userId == user_id,
                        ),
                    ),
                )
                if not doc_info:
                    logger.error("[DocumentManager] 文件不存在: %s", doc)
                    continue

                conv_doc = await session.scalars(
                    select(ConversationDocument).where(
                        and_(
                            ConversationDocument.documentId == doc,
                            ConversationDocument.isUnused.is_(True),
                        ),
                    ),
                )
                if not conv_doc:
                    logger.error("[DocumentManager] 文件不存在或已使用: %s", doc)
                    continue

                await session.delete(conv_doc)
                await session.delete(doc_info)
                await session.commit()

                # 删除MinIO内文件
                await asyncer.asyncify(DocumentManager._remove_doc_from_minio)(doc)


    @staticmethod
    async def delete_document_by_conversation_id(user_id: str, conversation_id: uuid.UUID) -> list[str]:
        """通过ConversationID删除文件"""
        doc_ids = []

        async with postgres.session() as session:
            docs = (await session.scalars(
                select(Document).where(Document.conversationId == conversation_id),
            )).all()

            for doc in docs:
                await asyncer.asyncify(DocumentManager._remove_doc_from_minio)(str(doc.id))
                await session.delete(doc)
            await session.commit()

        session_id = await SessionManager.get_session_by_user(user_id)
        if not session_id:
            logger.error("[DocumentManager] Session不存在: %s", user_id)
            return []
        await KnowledgeBaseService.delete_doc_from_rag(session_id, doc_ids)
        return doc_ids


    @staticmethod
    async def get_doc_count(conversation_id: uuid.UUID) -> int:
        """获取对话文件数量"""
        async with postgres.session() as session:
            return (await session.scalars(
                select(func.count(ConversationDocument.id)).where(
                    ConversationDocument.conversationId == conversation_id,
                ),
            )).one()


    @staticmethod
    async def change_doc_status(user_id: str, conversation_id: uuid.UUID) -> None:
        """文件状态由unused改为used"""
        async with postgres.session() as session:
            conversation = (await session.scalars(
                select(Conversation).where(
                    and_(
                        Conversation.id == conversation_id,
                        Conversation.userId == user_id,
                    ),
                ),
            )).one_or_none()
            if not conversation:
                logger.error("[DocumentManager] 对话不存在: %s", conversation_id)
                return

            # 把unused_docs加入RecordGroup中，并与问题关联
            docs = (await session.scalars(
                select(ConversationDocument).where(
                    and_(
                        ConversationDocument.conversationId == conversation_id,
                        ConversationDocument.isUnused.is_(True),
                    ),
                ),
            )).all()
            if not docs:
                return

            for doc in docs:
                doc.isUnused = False
            await session.commit()


    @staticmethod
    async def save_answer_doc(user_id: str, record_id: uuid.UUID, doc_infos: list[ConversationDocument]) -> None:
        """保存与答案关联的文件（使用PostgreSQL）"""
        async with postgres.session() as session:
            # 查询对应的Record
            record = (await session.scalars(
                select(Record).where(
                    and_(
                        Record.id == record_id,
                        Record.userId == user_id,
                    ),
                ),
            )).one_or_none()
            if not record:
                logger.error("[DocumentManager] 记录不存在或非当前用户: %s", record_id)
                return

            # 更新ConversationDocument表，将对应的doc与recordId关联，并设置为已使用
            for doc_info in doc_infos:
                doc = (await session.scalars(
                    select(ConversationDocument).where(ConversationDocument.id == doc_info.id),
                )).one_or_none()

                if doc:
                    doc.isUnused = False
                    doc.associated = ConvDocAssociated.ANSWER
                    doc.recordId = record_id
            await session.commit()
