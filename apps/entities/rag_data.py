"""请求RAG相关接口时，使用的数据类型

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Literal, Optional

from pydantic import BaseModel


class RAGQueryReq(BaseModel):
    """查询RAG时的POST请求体"""

    question: str
    history: list[dict[str, str]] = []
    language: str = "zh"
    kb_sn: Optional[str] = None
    top_k: int = 5
    fetch_source: bool = False
    document_ids: list[str] = []


class RAGFileParseReqItem(BaseModel):
    """请求RAG处理文件时的POST请求体中的文件项"""

    id: str
    name: str
    bucket_name: str
    type: str


class RAGEventData(BaseModel):
    """RAG服务返回的事件数据"""

    content: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class RAGFileParseReq(BaseModel):
    """请求RAG处理文件时的POST请求体"""

    document_list: list[RAGFileParseReqItem]


class RAGFileStatusRspItem(BaseModel):
    """RAG处理文件状态的GET请求返回体"""

    id: str
    status: Literal["pending", "running", "success", "failed"]
