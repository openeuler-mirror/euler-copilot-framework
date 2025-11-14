# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MongoDB 连接器"""

import logging
import urllib.parse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymongo.asynchronous.client_session import AsyncClientSession
    from pymongo.asynchronous.collection import AsyncCollection

from apps.common.config import Config

logger = logging.getLogger(__name__)


class MongoDB:
    from pymongo import AsyncMongoClient
    """MongoDB连接器"""
    _client: "AsyncMongoClient" = AsyncMongoClient(
        f"mongodb://{urllib.parse.quote_plus(Config().get_config().mongodb.user)}:{urllib.parse.quote_plus(Config().get_config().mongodb.password)}@{Config().get_config().mongodb.host}:{Config().get_config().mongodb.port}/?directConnection=true",
    )

    @staticmethod
    def get_collection(collection_name: str) -> "AsyncCollection":
        """
        获取MongoDB集合

        :param str collection_name: 集合名称
        :return: 集合对象
        :rtype: AsyncCollection
        """
        return MongoDB._client[Config().get_config().mongodb.database][collection_name]

    @staticmethod
    async def clear_collection(collection_name: str) -> None:
        """
        清空MongoDB集合

        :param str collection_name: 集合名称
        :return: 无
        """
        await MongoDB._client[Config().get_config().mongodb.database][collection_name].delete_many({})

    @staticmethod
    def get_session() -> "AsyncClientSession":
        """
        获取MongoDB会话

        一个Client可以创建多个会话，一个会话一般用于一个事务。

        :return: 会话对象
        :rtype: AsyncClientSession
        """
        return MongoDB._client.start_session()
