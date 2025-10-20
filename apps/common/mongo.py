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
    """MongoDB连接器"""

    def __init__(self) -> None:
        """初始化MongoDB连接器"""
        from pymongo import AsyncMongoClient

        self._client = AsyncMongoClient(
            f"mongodb://{urllib.parse.quote_plus(Config().get_config().mongodb.user)}:{urllib.parse.quote_plus(Config().get_config().mongodb.password)}@{Config().get_config().mongodb.host}:{Config().get_config().mongodb.port}/?directConnection=true",
        )


    def get_collection(self, collection_name: str) -> "AsyncCollection":
        """
        获取MongoDB集合

        :param str collection_name: 集合名称
        :return: 集合对象
        :rtype: AsyncCollection
        """
        return self._client[Config().get_config().mongodb.database][collection_name]


    async def clear_collection(self, collection_name: str) -> None:
        """
        清空MongoDB集合

        :param str collection_name: 集合名称
        :return: 无
        """
        await self._client[Config().get_config().mongodb.database][collection_name].delete_many({})


    def get_session(self) -> "AsyncClientSession":
        """
        获取MongoDB会话

        一个Client可以创建多个会话，一个会话一般用于一个事务。

        :return: 会话对象
        :rtype: AsyncClientSession
        """
        return self._client.start_session()
