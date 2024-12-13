# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import json
import aiohttp

from apps.common.config import config
from apps.service import Activity


class RAG:
    """
    调用RAG服务，获取知识库答案
    """

    def __init__(self):
        raise NotImplementedError("RAG类无法被实例化！")

    @staticmethod
    async def get_rag_result(user_sub: str, question: str, language: str, history: list):
        url = config["RAG_HOST"].rstrip("/") + "/kb/get_stream_answer"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "question": question,
            "history": history,
            "language": language,
            "kb_sn": f'{language}_default_test',
            "top_k": 5,
            "fetch_source": False
        }
        if config['RAG_KB_SN']:
            data.update({"kb_sn": config['RAG_KB_SN']})
        payload = json.dumps(data, ensure_ascii=False)

        yield "data: " + json.dumps({"content": "正在查询知识库，请稍等...\n\n"}) + "\n\n"
        # asyncio HTTP请求
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
            async with session.post(url, headers=headers, data=payload, ssl=False) as response:
                async for line in response.content:
                    line_str = line.decode('utf-8')

                    if line_str != "data: [DONE]" and Activity.is_active(user_sub):
                        yield line_str
                    else:
                        return
