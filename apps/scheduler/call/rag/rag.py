# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""RAG工具：查询知识库"""

import logging
import uuid
from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import Any

import httpx
from fastapi import status
from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field

from apps.common.config import config
from apps.llm import json_generator
from apps.models import LanguageType
from apps.scheduler.call.core import CoreCall
from apps.schemas.enum_var import CallOutputType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)
from apps.services.document import DocumentManager

from .func import QUESTION_REWRITE_FUNCTION
from .schema import (
    DocItem,
    QuestionRewriteOutput,
    RAGInput,
    RAGOutput,
    SearchMethod,
)

_logger = logging.getLogger(__name__)


class RAG(CoreCall, input_model=RAGInput, output_model=RAGOutput):
    """RAG工具：查询知识库"""

    kb_ids: list[uuid.UUID] = Field(description="知识库的id列表", default=[])
    top_k: int = Field(description="返回的分片数量", default=5)
    doc_ids: list[str] | None = Field(description="文档id列表", default=None)
    search_method: str = Field(description="检索方法", default=SearchMethod.KEYWORD_AND_VECTOR.value)
    is_related_surrounding: bool = Field(description="是否关联上下文", default=True)
    is_classify_by_doc: bool = Field(description="是否按文档分类", default=False)
    is_rerank: bool = Field(description="是否重新排序", default=False)
    is_compress: bool = Field(description="是否压缩", default=False)
    tokens_limit: int = Field(description="token限制", default=8192)
    history_len: int = Field(description="历史对话长度", default=3)


    @classmethod
    def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
        """返回Call的名称和描述"""
        i18n_info = {
            LanguageType.CHINESE: CallInfo(
                name="知识库", description="查询知识库，从文档中获取必要信息",
            ),
            LanguageType.ENGLISH: CallInfo(
                name="Knowledge Base",
                description="Query the knowledge base and obtain necessary information from documents.",
            ),
        }
        return i18n_info[language]


    async def _init(self, call_vars: CallVars) -> RAGInput:
        """初始化RAG工具"""
        if not call_vars.ids.auth_header:
            err = "[RAG] 未设置Auth Header"
            _logger.error(err)
            raise CallError(message=err, data={})

        return RAGInput(
            kbIds=self.kb_ids,
            topK=self.top_k,
            query=call_vars.question,
            docIds=self.doc_ids,
            searchMethod=self.search_method,
            isRelatedSurrounding=self.is_related_surrounding,
            isClassifyByDoc=self.is_classify_by_doc,
            isRerank=self.is_rerank,
            isCompress=self.is_compress,
            tokensLimit=self.tokens_limit,
        )


    async def _fetch_doc_chunks(self, data: RAGInput) -> list[DocItem]:
        """从知识库获取文档分片"""
        url = config.rag.rag_service.rstrip("/") + "/chunk/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._sys_vars.ids.auth_header}",
        }

        doc_chunk_list = []
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                data_json = data.model_dump(exclude_none=True, by_alias=True)
                response = await client.post(url, headers=headers, json=data_json)
                # 检查响应状态码
                if response.status_code == status.HTTP_200_OK:
                    result = response.json()
                    # 对返回的docChunks进行校验
                    try:
                        validated_chunks = []
                        for chunk_data in result["result"]["docChunks"]:
                            validated_chunk = DocItem.model_validate(chunk_data)
                            validated_chunks.append(validated_chunk)
                        doc_chunk_list += validated_chunks
                    except Exception:
                        _logger.exception("[RAG] chunk校验失败")
                        raise
        except Exception:
            _logger.exception("[RAG] 获取文档分片失败")

        return doc_chunk_list


    async def _get_temp_docs(self, conversation_id: uuid.UUID) -> list[str]:
        """获取当前会话的临时文档"""
        doc_ids = []
        # 从Conversation中获取刚上传的文档
        docs = await DocumentManager.get_unused_docs(conversation_id)
        # 从最近10条Record中获取文档
        docs += await DocumentManager.get_used_docs(conversation_id, 10, "question")
        doc_ids += [doc.id for doc in docs]
        return doc_ids


    async def _get_doc_info(self, doc_ids: list[str], data: RAGInput) -> list[DocItem]:
        """获取文档信息，支持临时文档和知识库文档"""
        doc_chunk_list: list[DocItem] = []

        # 处理临时文档：若docIds为空，则不请求
        if doc_ids:
            tmp_data = deepcopy(data)
            tmp_data.kbIds = [uuid.UUID("00000000-0000-0000-0000-000000000000")]
            tmp_data.docIds = doc_ids
            _logger.info("[RAG] 获取临时文档: %s", tmp_data.docIds)
            doc_chunk_list.extend(await self._fetch_doc_chunks(tmp_data))
        else:
            _logger.info("[RAG] docIds为空，跳过临时文档请求")

        # 处理知识库：若kbIds为空，则不请求
        if data.kbIds:
            kb_data = deepcopy(data)
            # 知识库查询时不使用docIds，只使用kbIds
            kb_data.docIds = None
            _logger.info("[RAG] 获取知识库文档: %s", kb_data.kbIds)
            doc_chunk_list.extend(await self._fetch_doc_chunks(kb_data))
        else:
            _logger.info("[RAG] kbIds为空，跳过知识库请求")

        return doc_chunk_list


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """调用RAG工具"""
        data = RAGInput(**input_data)
        # 使用Jinja2渲染问题重写模板，并用json_generator解析结果
        try:
            env = SandboxedEnvironment(
                loader=BaseLoader(),
                autoescape=False,
                trim_blocks=True,
                lstrip_blocks=True,
            )
            tmpl = env.from_string(self._load_prompt("question_rewrite"))
            prompt = tmpl.render(question=data.query)

            # 使用json_generator直接获取JSON结果
            json_result = await json_generator.generate(
                function=QUESTION_REWRITE_FUNCTION[self._sys_vars.language],
                conversation=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    *self._sys_vars.background.conversation[-self.history_len:],
                ],
                prompt=prompt,
            )
            # 直接使用解析后的JSON结果
            data.query = QuestionRewriteOutput.model_validate(json_result).question
        except Exception:
            _logger.exception("[RAG] 问题重写失败，使用原始问题")

        # 获取临时文档ID列表
        if self._sys_vars.ids.conversation_id:
            temp_doc_ids = await self._get_temp_docs(self._sys_vars.ids.conversation_id)
        else:
            temp_doc_ids = []

        # 合并传入的doc_ids和临时文档ID
        all_doc_ids = list(set((data.docIds or []) + temp_doc_ids))

        # 获取文档片段
        doc_chunk_list = await self._get_doc_info(all_doc_ids, data)

        yield CallOutputChunk(
            type=CallOutputType.DATA,
            content=RAGOutput(
                question=data.query,
                corpus=doc_chunk_list,
            ).model_dump(exclude_none=True, by_alias=True),
        )
