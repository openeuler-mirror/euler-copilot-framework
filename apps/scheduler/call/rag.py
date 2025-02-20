"""RAG工具：查询知识库

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

from pydantic import BaseModel, Field

from apps.scheduler.call.core import CoreCall


class _RAGParams(BaseModel):
    """RAG工具的参数"""

    question: str = Field(description="用户的问题")


class _RAGOutput(BaseModel):
    """RAG工具的输出"""

    message: str = Field(description="RAG工具的输出")


class RAG(metaclass=CoreCall, param_cls=_RAGParams, output_cls=_RAGOutput):
    """RAG工具：查询知识库"""

    name: str = "rag"
    description: str = "RAG工具，用于查询知识库"

    async def __call__(self, _slot_data: dict[str, Any]):
        """调用RAG工具"""
