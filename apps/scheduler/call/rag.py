"""RAG工具：查询知识库

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, ClassVar, Optional

import aiohttp
from fastapi import status
from pydantic import BaseModel, Field

from apps.common.config import config
from apps.entities.scheduler import CallError, CallVars
from apps.scheduler.call.core import CoreCall


class _RAGOutput(BaseModel):
    """RAG工具的输出"""

    corpus: list[str] = Field(description="知识库的语料列表")


class RAG(CoreCall):
    """RAG工具：查询知识库"""

    name: ClassVar[str] = "知识库"
    description: ClassVar[str] = "查询知识库，从文档中获取必要信息"

    knowledge_base: str = Field(description="知识库的id", alias="kb_sn", default=None)
    top_k: int = Field(description="返回的答案数量(经过整合以及上下文关联)", default=5)
    retrieval_mode: str = Field(description="检索模式", default="chunk", choices=['chunk', 'full_text'])


    async def exec(self, syscall_vars: CallVars, **kwargs: Any) -> _RAGOutput:
        """调用RAG工具"""
        syscall_vars: SysCallVars = getattr(self, "_syscall_vars")
        params: _RAGParams = getattr(self, "_params")

        params_dict = params.model_dump(exclude_none=True, by_alias=True)
        params_dict["content"] = syscall_vars.question
        url = config["RAG_HOST"].rstrip("/") + "/chunk/get"
        headers = {
            "Content-Type": "application/json",
        }

        # 发送 GET 请求
        session = aiohttp.ClientSession()
        async with session.post(url, headers=headers, json=params_dict) as response:
            # 检查响应状态码
            if response.status == status.HTTP_200_OK:
                result = await response.json()
                chunk_list = result["data"]
                for chunk in chunk_list:
                    chunk=chunk.replace("\n", " ")
                return _RAGOutput(
                    output=_RAGOutputList(corpus=chunk_list),
                )
            text = await response.text()
            raise CallError(
                message=f"rag调用失败：{text}",
                data={
                    "question": syscall_vars.question,
                    "status": response.status,
                    "text": text,
                },
            )
