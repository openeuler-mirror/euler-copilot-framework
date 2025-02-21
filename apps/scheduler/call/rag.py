"""RAG工具：查询知识库

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, List, Optional

from pydantic import BaseModel, Field

import aiohttp

from apps.scheduler.call.core import CoreCall

from apps.entities.scheduler import CallError, SysCallVars

from apps.common.config import config


class _RAGParams(BaseModel):
    """RAG工具的参数"""

    knowledge_base: str = Field(description="知识库的id")
    top_k: int = Field(description="返回的答案数量(经过整合以及上下文关联)", default=5)
    methods: Optional[List[str]] = Field(description="rag检索方法")


class _RAGOutput(BaseModel):
    """RAG工具的输出"""

    message: List[str] = Field(description="RAG工具的输出")


class RAG(metaclass=CoreCall, param_cls=_RAGParams, output_cls=_RAGOutput):
    """RAG工具：查询知识库"""

    name: str = "rag"
    description: str = "RAG工具，用于查询知识库"

    async def __call__(self, _slot_data: dict[str, Any]):
        """调用RAG工具"""
        syscall_vars: SysCallVars = getattr(self, "_syscall_vars")
        params: _RAGParams = getattr(self, "_params")

        question = syscall_vars.question

        # 资产库ID
        kb_sn = params.knowledge_base
        # 获取chunk的数量
        top_k = params.top_k

        url = config["RAG_HOST"].rstrip("/") + "/chunk/get"

        headers = {
            "Content-Type": "application/json",
        }

        params = {
            "question": question,
            "kb_sn": kb_sn,
            "top_k": top_k
        }

        try:
            # 发送 GET 请求
            session = aiohttp.ClientSession()
            async with session.get(url, headers=headers, params=params) as response:
                # 检查响应状态码
                if response.status_code == 200:
                    result = await response.json()
                    chunk_list = result['data']
                else:
                    text = await response.text()
                    raise CallError(message=f"rag调用失败：{text}", data={})
        except Exception as e:
            raise CallError(message=f"rag调用失败：{e!s}", data={}) from e
        return _RAGOutput(message=chunk_list)
