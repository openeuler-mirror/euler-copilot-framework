"""RAG工具：查询知识库

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import logging
from typing import Any, ClassVar, Literal

import aiohttp
from fastapi import status
from pydantic import BaseModel, Field

from apps.common.config import config
from apps.entities.scheduler import CallError, CallVars
from apps.scheduler.call.core import CoreCall

logger = logging.getLogger("ray")


class RAGOutput(BaseModel):
    """RAG工具的输出"""

    corpus: list[str] = Field(description="知识库的语料列表")


class RAG(CoreCall, ret_type=RAGOutput):
    """RAG工具：查询知识库"""

    name: ClassVar[str] = "知识库"
    description: ClassVar[str] = "查询知识库，从文档中获取必要信息"

    knowledge_base: str = Field(description="知识库的id", alias="kb_sn", default=None)
    top_k: int = Field(description="返回的答案数量(经过整合以及上下文关联)", default=5)
    retrieval_mode: Literal["chunk", "full_text"] = Field(description="检索模式", default="chunk")


    async def init(self, syscall_vars: CallVars, **_kwargs: Any) -> dict[str, Any]:
        """初始化RAG工具"""
        self._params_dict = {
            "kb_sn": self.knowledge_base,
            "top_k": self.top_k,
            "retrieval_mode": self.retrieval_mode,
            "content": syscall_vars.question,
        }

        self._url = config["RAG_HOST"].rstrip("/") + "/chunk/get"
        self._headers = {
            "Content-Type": "application/json",
        }

        return self._params_dict


    async def exec(self) -> dict[str, Any]:
        """调用RAG工具"""
        # 发送 GET 请求
        async with aiohttp.ClientSession() as session, session.post(self._url, headers=self._headers, json=self._params_dict) as response:
            # 检查响应状态码
            if response.status == status.HTTP_200_OK:
                result = await response.json()
                chunk_list = result["data"]

                corpus = []
                for chunk in chunk_list:
                    clean_chunk = chunk.replace("\n", " ")
                    corpus.append(clean_chunk)

                return RAGOutput(
                    corpus=corpus,
                ).model_dump(exclude_none=True, by_alias=True)

            text = await response.text()
            logger.error("[RAG] 调用失败：%s", text)

            raise CallError(
                message=f"rag调用失败：{text}",
                data={
                    "question": self._params_dict["content"],
                    "status": response.status,
                    "text": text,
                },
            )
