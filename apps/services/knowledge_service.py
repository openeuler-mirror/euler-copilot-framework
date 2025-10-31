# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""文件上传至RAG，作为临时语料"""

import logging
import uuid

import httpx
from fastapi import status

from apps.common.config import config
from apps.models import Document
from apps.schemas.rag_data import (
    RAGFileParseReq,
    RAGFileParseReqItem,
    RAGFileStatusRspItem,
)

logger = logging.getLogger(__name__)
rag_host = config.rag.rag_service
_RAG_DOC_PARSE_URI = rag_host.rstrip("/") + "/doc/temporary/parser"
_RAG_DOC_STATUS_URI = rag_host.rstrip("/") + "/doc/temporary/status"
_RAG_DOC_DELETE_URI = rag_host.rstrip("/") + "/doc/temporary/delete"


class KnowledgeBaseService:
    """知识库服务"""

    @staticmethod
    async def send_file_to_rag(auth_header: str, docs: list[Document]) -> list[str]:
        """上传文件给RAG，进行处理和向量化"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_header}",
        }
        rag_docs = [RAGFileParseReqItem(
            id=str(doc.id),
            name=doc.name,
            bucket_name="document",
            type=doc.extension,
        )
            for doc in docs
        ]
        post_data = RAGFileParseReq(
            document_list=rag_docs).model_dump(exclude_none=True, by_alias=True)

        async with httpx.AsyncClient() as client:
            resp = await client.post(_RAG_DOC_PARSE_URI, headers=headers, json=post_data, timeout=30.0)
            resp_data = resp.json()
            if resp.status_code != status.HTTP_200_OK:
                return []
            return resp_data["result"]

    @staticmethod
    async def delete_doc_from_rag(auth_header: str, doc_ids: list[str]) -> list[str]:
        """删除文件"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_header}",
        }
        delete_data = {"ids": doc_ids}
        async with httpx.AsyncClient() as client:
            resp = await client.post(_RAG_DOC_DELETE_URI, headers=headers, json=delete_data, timeout=30.0)
            resp_data = resp.json()
            if resp.status_code != status.HTTP_200_OK:
                return []
            return resp_data["result"]

    @staticmethod
    async def get_doc_status_from_rag(auth_header: str, doc_ids: list[uuid.UUID]) -> list[RAGFileStatusRspItem]:
        """获取文件状态"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_header}",
        }
        post_data = {"ids": doc_ids}
        async with httpx.AsyncClient() as client:
            resp = await client.post(_RAG_DOC_STATUS_URI, headers=headers,  json=post_data, timeout=30.0)
            resp_data = resp.json()
            if resp.status_code != status.HTTP_200_OK:
                return []
            return [RAGFileStatusRspItem.model_validate(item) for item in resp_data["result"]]
