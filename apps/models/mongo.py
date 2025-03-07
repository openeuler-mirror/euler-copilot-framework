"""MongoDB 连接

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from __future__ import annotations

import logging
import urllib.parse
from typing import TYPE_CHECKING

from pymongo import AsyncMongoClient

from apps.common.config import config

logger = logging.getLogger("ray")


if TYPE_CHECKING:
    from pymongo.asynchronous.client_session import AsyncClientSession
    from pymongo.asynchronous.collection import AsyncCollection


class MongoDB:
    """MongoDB连接"""

    _client: AsyncMongoClient = AsyncMongoClient(
        f"mongodb://{urllib.parse.quote_plus(config['MONGODB_USER'])}:{urllib.parse.quote_plus(config['MONGODB_PWD'])}@{config['MONGODB_HOST']}:{config['MONGODB_PORT']}/?directConnection=true&replicaSet=rs0",
    )

    @classmethod
    def get_collection(cls, collection_name: str) -> AsyncCollection:
        """获取MongoDB集合（表）"""
        try:
            return cls._client[config["MONGODB_DATABASE"]][collection_name]
        except Exception as e:
            logger.exception("[MongoDB] 获取集合 %s 失败", collection_name)
            raise RuntimeError(str(e)) from e

    @classmethod
    async def clear_collection(cls, collection_name: str) -> None:
        """清空MongoDB集合（表）"""
        try:
            await cls._client[config["MONGODB_DATABASE"]][collection_name].delete_many({})
        except Exception:
            logger.exception("[MongoDB] 清空集合 %s 失败", collection_name)

    @classmethod
    def get_session(cls) -> AsyncClientSession:
        """获取MongoDB会话"""
        return cls._client.start_session()
