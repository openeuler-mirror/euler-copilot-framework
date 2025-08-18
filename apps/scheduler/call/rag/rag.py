# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""RAG工具：查询知识库"""

import logging
from collections.abc import AsyncGenerator
from typing import Any, ClassVar

import httpx
from fastapi import status
from pydantic import Field

from apps.common.config import Config
from apps.llm.patterns.rewrite import QuestionRewrite
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.rag.schema import RAGInput, RAGOutput, SearchMethod
from apps.schemas.enum_var import CallOutputType, LanguageType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)

logger = logging.getLogger(__name__)


class RAG(CoreCall, input_model=RAGInput, output_model=RAGOutput):
    """RAG工具：查询知识库"""

    knowledge_base_ids: list[str] = Field(description="知识库的id列表", default=[])
    top_k: int = Field(description="返回的分片数量", default=5)
    document_ids: list[str] | None = Field(description="文档id列表", default=None)
    search_method: str = Field(description="检索方法", default=SearchMethod.KEYWORD_AND_VECTOR.value)
    is_related_surrounding: bool = Field(description="是否关联上下文", default=True)
    is_classify_by_doc: bool = Field(description="是否按文档分类", default=False)
    is_rerank: bool = Field(description="是否重新排序", default=False)
    is_compress: bool = Field(description="是否压缩", default=False)
    tokens_limit: int = Field(description="token限制", default=8192)

    i18n_info: ClassVar[dict[str, dict]] = {
        LanguageType.CHINESE: {
            "name": "知识库",
            "description": "查询知识库，从文档中获取必要信息",
        },
        LanguageType.ENGLISH: {
            "name": "Knowledge Base",
            "description": "Query the knowledge base and obtain necessary information from documents",
        },
    }

    async def _init(self, call_vars: CallVars) -> RAGInput:
        """初始化RAG工具"""
        return RAGInput(
            session_id=call_vars.ids.session_id,
            kbIds=self.knowledge_base_ids,
            topK=self.top_k,
            query=call_vars.question,
            docIds=self.document_ids,
            searchMethod=self.search_method,
            isRelatedSurrounding=self.is_related_surrounding,
            isClassifyByDoc=self.is_classify_by_doc,
            isRerank=self.is_rerank,
            isCompress=self.is_compress,
            tokensLimit=self.tokens_limit,
        )

    async def _exec(
        self, input_data: dict[str, Any], language: LanguageType = LanguageType.CHINESE
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """调用RAG工具"""
        data = RAGInput(**input_data)
        question_obj = QuestionRewrite()
        question = await question_obj.generate(question=data.question)
        data.question = question
        self.tokens.input_tokens += question_obj.input_tokens
        self.tokens.output_tokens += question_obj.output_tokens

        url = Config().get_config().rag.rag_service.rstrip("/") + "/chunk/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {data.session_id}",
        }

        # 发送请求
        data_json = data.model_dump(exclude_none=True, by_alias=True)
        del data_json["session_id"]
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(url, headers=headers, json=data_json)

            # 检查响应状态码
            if response.status_code == status.HTTP_200_OK:
                result = response.json()
                doc_chunk_list = result["result"]["docChunks"]

                corpus = []
                for doc_chunk in doc_chunk_list:
                    for chunk in doc_chunk["chunks"]:
                        corpus.extend([chunk["text"].replace("\n", "")])

                yield CallOutputChunk(
                    type=CallOutputType.DATA,
                    content=RAGOutput(
                        question=data.question,
                        corpus=corpus,
                    ).model_dump(exclude_none=True, by_alias=True),
                )
                return

            text = response.text
            logger.error("[RAG] 调用失败：%s", text)

            raise CallError(
                message=f"rag调用失败：{text}",
                data={
                    "question": data.question,
                    "status": response.status_code,
                    "text": text,
                },
            )
