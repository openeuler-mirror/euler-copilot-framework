# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MongoDB 连接器"""

import logging
import urllib.parse
from typing import TYPE_CHECKING
import os
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
        maxPoolSize=os.cpu_count() * 2,
        minPoolSize=5,           # 最小保持连接数
        maxIdleTimeMS=300000,    # 连接最大空闲时间（5分钟）
        maxConnecting=10,        # 最大并发连接创建数

        # 超时设置
        serverSelectionTimeoutMS=15000,  # 服务器选择超时（15秒）
        socketTimeoutMS=300000,  # socket读写超时（5分钟）
        connectTimeoutMS=15000,         # 连接建立超时（15秒）

        # 重试机制
        retryWrites=True,        # 支持写操作重试
        retryReads=True,         # 支持读操作重试

        # 心跳检测
        heartbeatFrequencyMS=5000,  # 服务器心跳检测间隔（5秒）
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
