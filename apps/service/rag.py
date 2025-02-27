"""对接Euler Copilot RAG

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
import logging
from collections.abc import AsyncGenerator

import aiohttp
from fastapi import status

from apps.common.config import config
from apps.entities.rag_data import RAGQueryReq
from apps.service import Activity

logger = logging.getLogger(__name__)

class RAG:
    """调用RAG服务，获取知识库答案"""

    @staticmethod
    async def get_rag_result(user_sub: str, data: RAGQueryReq) -> AsyncGenerator[str, None]:
        """获取RAG服务的结果"""
        url = config["RAG_HOST"].rstrip("/") + "/kb/get_stream_answer"
        headers = {
            "Content-Type": "application/json",
        }

        payload = json.dumps(data.model_dump(exclude_none=True, by_alias=True), ensure_ascii=False)


        # asyncio HTTP请求
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session, session.post(
            url, headers=headers, data=payload, ssl=False,
        ) as response:
            if response.status != status.HTTP_200_OK:
                logger.error("[RAG] RAG服务返回错误码: %s\n%s", response.status, await response.text())
                return

            async for line in response.content:
                line_str = line.decode("utf-8")

                if not await Activity.is_active(user_sub):
                    return

                if "data: [DONE]" in line_str:
                    return

                yield line_str
