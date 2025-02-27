"""文件Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import base64
import logging
import uuid
from typing import Optional

import asyncer
import magic
from fastapi import UploadFile

from apps.entities.collection import (
    Conversation,
    Document,
    RecordGroup,
    RecordGroupDocument,
)
from apps.entities.record import RecordDocument
from apps.models.minio import MinioClient
from apps.models.mongo import MongoDB
from apps.service import KnowledgeBaseService

logger = logging.getLogger("ray")


class DocumentManager:
    """文件相关操作"""

    @classmethod
    def _storage_single_doc_minio(cls, file_id: str, document: UploadFile) -> str:
        """存储单个文件到MinIO"""
        MinioClient.check_bucket("document")

        # 获取文件MIME
        file = document.file
        mime = magic.from_buffer(file.read(), mime=True)
        file.seek(0)

        # 上传到MinIO
        MinioClient.upload_file(
            bucket_name="document",
            object_name=file_id,
            data=file,
            content_type=mime,
            length=-1,
            part_size=10*1024*1024,
            metadata={
                "file_name": base64.b64encode(document.filename.encode("utf-8")).decode("ascii"),  # type: ignore[arg-type]
            },
        )
        return mime


    @classmethod
    async def storage_docs(cls, user_sub: str, conversation_id: str, documents: list[UploadFile]) -> list[Document]:
        """存储多个文件"""
        uploaded_files = []
        doc_collection = MongoDB.get_collection("document")
        conversation_collection = MongoDB.get_collection("conversation")
        for document in documents:
            try:
                if document.filename is None or document.size is None:
                    continue

                file_id = str(uuid.uuid4())
                mime = await asyncer.asyncify(cls._storage_single_doc_minio)(file_id, document)

                # 保存到MongoDB
                doc_info = Document(
                    _id=file_id,
                    user_sub=user_sub,
                    name=document.filename,
                    type=mime,
                    size=document.size / 1024.0,
                    conversation_id=conversation_id,
                )
                await doc_collection.insert_one(doc_info.model_dump(by_alias=True))
                await conversation_collection.update_one({"_id": conversation_id}, {
                    "$push": {"unused_docs": file_id},
                })

                # 准备返回值
                uploaded_files.append(doc_info)
            except Exception:
                logger.exception("[DocumentManager] 上传文件失败")

        return uploaded_files

    @classmethod
    async def get_unused_docs(cls, user_sub: str, conversation_id: str) -> list[Document]:
        """获取Conversation中未使用的文件"""
        conv_collection = MongoDB.get_collection("conversation")
        doc_collection = MongoDB.get_collection("document")

        try:
            conv = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
            if not conv:
                logger.error("[DocumentManager] 对话不存在: %s", conversation_id)
                return []

            docs_ids = conv.get("unused_docs", [])
            return [Document(**doc) async for doc in doc_collection.find({"_id": {"$in": docs_ids}})]
        except Exception:
            logger.exception("[DocumentManager] 获取未使用文件失败")
            return []

    @classmethod
    async def get_used_docs_by_record_group(cls, user_sub: str, record_group_id: str) -> list[RecordDocument]:
        """获取RecordGroup关联的文件"""
        record_group_collection = MongoDB.get_collection("record_group")
        docs_collection = MongoDB.get_collection("document")
        try:
            record_group = await record_group_collection.find_one({"_id": record_group_id, "user_sub": user_sub})
            if not record_group:
                logger.error("[DocumentManager] 记录组不存在: %s", record_group_id)
                return []

            doc_ids = RecordGroup.model_validate(record_group).docs
            doc_infos = [Document.model_validate(doc) async for doc in docs_collection.find({"_id": {"$in": doc_ids}})]
            return [
                RecordDocument(
                    _id=item[0].id,
                    name=item[1].name,
                    type=item[1].type,
                    size=item[1].size,
                    conversation_id=item[1].conversation_id,
                    associated=item[0].associated,
                ) for item in zip(doc_ids, doc_infos)
            ]
        except Exception:
            logger.exception("[DocumentManager] 获取使用文件失败")
            return []

    @classmethod
    async def get_used_docs(cls, user_sub: str, conversation_id: str, record_num: Optional[int] = 10) -> list[Document]:
        """获取最后n次问答所用到的文件"""
        docs_collection = MongoDB.get_collection("document")
        record_group_collection = MongoDB.get_collection("record_group")
        try:
            if record_num:
                record_groups = record_group_collection.find({"conversation_id": conversation_id, "user_sub": user_sub}).sort("created_at", -1).limit(record_num)
            else:
                record_groups = record_group_collection.find({"conversation_id": conversation_id, "user_sub": user_sub}).sort("created_at", -1)

            docs = []
            async for current_record_group in record_groups:
                for doc in RecordGroup.model_validate(current_record_group).docs:
                    docs += [doc.id]
            # 文件ID去重
            docs = list(set(docs))
            # 返回文件详细信息
            return [Document.model_validate(doc) async for doc in docs_collection.find({"_id": {"$in": docs}})]
        except Exception:
            logger.exception("[DocumentManager] 获取使用文件失败")
            return []

    @classmethod
    def _remove_doc_from_minio(cls, doc_id: str) -> None:
        """从MinIO中删除文件"""
        MinioClient.delete_file("document", doc_id)

    @classmethod
    async def delete_document(cls, user_sub: str, document_list: list[str]) -> bool:
        """从未使用文件列表中删除一个文件"""
        doc_collection = MongoDB.get_collection("document")
        conv_collection = MongoDB.get_collection("conversation")
        try:
            async with MongoDB.get_session() as session, await session.start_transaction():
                for doc in document_list:
                    doc_info = await doc_collection.find_one_and_delete({"_id": doc, "user_sub": user_sub}, session=session)
                    # 删除Document表内文件
                    if not doc_info:
                        logger.error("[DocumentManager] 文件不存在: %s", doc)
                        continue

                    # 删除MinIO内文件
                    await asyncer.asyncify(cls._remove_doc_from_minio)(doc)

                    # 删除Conversation内文件
                    conv = await conv_collection.find_one({"_id": doc_info["conversation_id"]}, session=session)
                    if conv:
                        await conv_collection.update_one({"_id": conv["_id"]}, {
                            "$pull": {"unused_docs": doc},
                        }, session=session)
                await session.commit_transaction()
                return True
        except Exception:
            logger.exception("[DocumentManager] 删除文件失败")
            return False

    @classmethod
    async def delete_document_by_conversation_id(cls, user_sub: str, conversation_id: str) -> list[str]:
        """通过ConversationID删除文件"""
        doc_collection = MongoDB.get_collection("document")
        doc_ids = []
        try:
            async with MongoDB.get_session() as session, await session.start_transaction():
                async for doc in doc_collection.find({"user_sub": user_sub, "conversation_id": conversation_id}, session=session):
                    doc_ids.append(doc["_id"])
                    await asyncer.asyncify(cls._remove_doc_from_minio)(doc["_id"])
                    await doc_collection.delete_one({"_id": doc["_id"]}, session=session)
                await session.commit_transaction()
                await KnowledgeBaseService.delete_doc_from_rag(doc_ids)
                return doc_ids
        except Exception:
            logger.exception("[DocumentManager] 通过ConversationID删除文件失败")
            return []


    @classmethod
    async def get_doc_count(cls, user_sub: str, conversation_id: str) -> int:
        """获取对话文件数量"""
        doc_collection = MongoDB.get_collection("document")
        return await doc_collection.count_documents({"user_sub": user_sub, "conversation_id": conversation_id})


    @classmethod
    async def change_doc_status(cls, user_sub: str, conversation_id: str, record_group_id: str) -> None:
        """文件状态由unused改为used"""
        record_group_collection = MongoDB.get_collection("record_group")
        conversation_collection = MongoDB.get_collection("conversation")
        try:
            # 查找Conversation中的unused_docs
            conversation = await conversation_collection.find_one({"user_sub": user_sub, "_id": conversation_id})
            if not conversation:
                logger.error("[DocumentManager] 对话不存在: %s", conversation_id)
                return

            # 把unused_docs加入RecordGroup中，并与问题关联
            docs_id = Conversation.model_validate(conversation).unused_docs
            for doc in docs_id:
                doc_info = RecordGroupDocument(_id=doc, associated="question")
                await record_group_collection.update_one({"_id": record_group_id, "user_sub": user_sub}, {"$push": {"docs": doc_info.model_dump(by_alias=True)}})

            # 把unused_docs从Conversation中删除
            await conversation_collection.update_one({"_id": conversation_id}, {"$set": {"unused_docs": []}})
        except Exception:
            logger.exception("[DocumentManager] 改变文件状态失败")


    @classmethod
    async def save_answer_doc(cls, user_sub: str, record_group_id: str, doc_ids: list[str]) -> None:
        """保存与答案关联的文件"""
        record_group_collection = MongoDB.get_collection("record_group")
        try:
            for doc_id in doc_ids:
                doc_info = RecordGroupDocument(_id=doc_id, associated="answer")
                await record_group_collection.update_one({"_id": record_group_id, "user_sub": user_sub}, {"$push": {"docs": doc_info.model_dump(by_alias=True)}})
        except Exception:
            logger.exception("[DocumentManager] 保存答案文件失败")


