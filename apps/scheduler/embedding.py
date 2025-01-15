"""从Vectorize获取向量化数据

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import aiohttp

from apps.common.config import config


async def get_embedding(text: list[str]) -> list[float]:
    """访问Vectorize的Embedding API，获得向量化数据

    :param text: 待向量化文本（多条文本组成List）
    :return: 文本对应的向量（顺序与text一致，也为List）
    """
    api = config["VECTORIZE_HOST"].rstrip("/") + "/embedding"

    async with aiohttp.ClientSession() as session, session.post(
        api, json={"texts": text}, timeout=30,
    ) as response:
        return await response.json()
