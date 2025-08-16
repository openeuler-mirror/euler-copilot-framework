# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""请求RAG相关接口时，使用的数据类型"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class RAGQueryReq(BaseModel):
    """查询RAG时的POST请求体"""

    kb_ids: list[str] = Field(default=[], description="资产id", alias="kbIds")
    query: str = Field(default="", description="查询内容")
    top_k: int = Field(default=5, description="返回的结果数量", alias="topK")
    doc_ids: list[str] | None = Field(default=None, description="文档id", alias="docIds")
    search_method: str = Field(default="dynamic_weighted_keyword_and_vector",
                                description="检索方法", alias="searchMethod")
    is_related_surrounding: bool = Field(default=True, description="是否关联上下文", alias="isRelatedSurrounding")
    is_classify_by_doc: bool = Field(default=True, description="是否按文档分类", alias="isClassifyByDoc")
    is_rerank: bool = Field(default=False, description="是否重新排序", alias="isRerank")
    tokens_limit: int | None = Field(default=None, description="token限制", alias="tokensLimit")


class RAGFileParseReqItem(BaseModel):
    """请求RAG处理文件时的POST请求体中的文件项"""

    id: str
    name: str
    bucket_name: str
    type: str


class RAGEventData(BaseModel):
    """RAG服务返回的事件数据"""

    content: Any
    event_type: str
    input_tokens: int = 0
    output_tokens: int = 0


class RAGFileParseReq(BaseModel):
    """请求RAG处理文件时的POST请求体"""

    document_list: list[RAGFileParseReqItem]


class RAGFileStatusRspItem(BaseModel):
    """RAG处理文件状态的GET请求返回体"""

    id: str
    status: Literal["pending", "running", "success", "failed"]
