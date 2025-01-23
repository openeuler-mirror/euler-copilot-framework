"""RAG工具：查询知识库

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

from typing import Any

from apps.scheduler.call.core import CoreCall


class RAG(metaclass=CoreCall):
    """RAG工具：查询知识库"""

    name: str = "rag"
    description: str = "RAG工具，用于查询知识库"

    async def __call__(self, _slot_data: dict[str, Any]):
        """调用RAG工具"""
