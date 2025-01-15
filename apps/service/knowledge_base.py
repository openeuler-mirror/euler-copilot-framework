"""文件上传至RAG，作为临时语料

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import aiohttp
from fastapi import status

from apps.common.config import config
from apps.entities.collection import Document
from apps.entities.rag_data import (
    RAGFileParseReq,
    RAGFileParseReqItem,
    RAGFileStatusRspItem,
)

_RAG_DOC_PARSE_URI = config["RAG_HOST"].rstrip("/") + "/doc/temporary/parser"
_RAG_DOC_STATUS_URI = config["RAG_HOST"].rstrip("/") + "/doc/temporary/status"
_RAG_DOC_DELETE_URI = config["RAG_HOST"].rstrip("/") + "/doc/temporary/delete"

class KnowledgeBaseService:
    """知识库服务"""

    @staticmethod
    async def send_file_to_rag(docs: list[Document]) -> list[str]:
        """上传文件给RAG，进行处理和向量化"""
        rag_docs = [RAGFileParseReqItem(
                id=doc.id,
                name=doc.name,
                bucket_name="document",
                type=doc.type,
            )
            for doc in docs
        ]
        post_data = RAGFileParseReq(document_list=rag_docs).model_dump(exclude_none=True, by_alias=True)

        async with aiohttp.ClientSession() as session, session.post(_RAG_DOC_PARSE_URI, json=post_data) as resp:
            resp_data = await resp.json()
            if resp.status != status.HTTP_200_OK:
                return []
            return resp_data["data"]

    @staticmethod
    async def delete_doc_from_rag(doc_ids: list[str]) -> list[str]:
        """删除文件"""
        post_data = {"ids": doc_ids}
        async with aiohttp.ClientSession() as session, session.post(_RAG_DOC_DELETE_URI, json=post_data) as resp:
            resp_data = await resp.json()
            if resp.status != status.HTTP_200_OK:
                return []
            return resp_data["data"]

    @staticmethod
    async def get_doc_status_from_rag(doc_ids: list[str]) -> list[RAGFileStatusRspItem]:
        """获取文件状态"""
        post_data = {"ids": doc_ids}
        async with aiohttp.ClientSession() as session, session.post(_RAG_DOC_STATUS_URI, json=post_data) as resp:
            resp_data = await resp.json()
            if resp.status != status.HTTP_200_OK:
                return []
            return [RAGFileStatusRspItem.model_validate(item) for item in resp_data["data"]]
