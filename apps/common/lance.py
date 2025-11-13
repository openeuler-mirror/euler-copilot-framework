# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""向LanceDB中存储向量化数据"""

import lancedb
from lancedb.db import AsyncConnection
from lancedb.index import HnswSq

from apps.common.config import Config
from apps.common.singleton import SingletonMeta
from apps.models.vector import (
    CallPoolVector,
    FlowPoolVector,
    NodePoolVector,
    ServicePoolVector,
)
from apps.schemas.mcp import MCPToolVector, MCPVector


class LanceDB(metaclass=SingletonMeta):
    """LanceDB向量化存储"""
    _engine: AsyncConnection | None = None

    @staticmethod
    async def init() -> None:
        """
        初始化LanceDB

        此步骤包含创建LanceDB引擎、建表等操作

        :return: 无
        """
        LanceDB._engine = await lancedb.connect_async(
            Config().get_config().deploy.data_dir.rstrip("/") + "/vectors",
        )

        # 创建表
        await LanceDB._engine.create_table(
            "flow",
            schema=FlowPoolVector,
            exist_ok=True,
        )
        await LanceDB.create_index("flow")
        await LanceDB._engine.create_table(
            "service",
            schema=ServicePoolVector,
            exist_ok=True,
        )
        await LanceDB.create_index("service")
        await LanceDB._engine.create_table(
            "call",
            schema=CallPoolVector,
            exist_ok=True,
        )
        await LanceDB.create_index("call")
        await LanceDB._engine.create_table(
            "node",
            schema=NodePoolVector,
            exist_ok=True,
        )
        await LanceDB.create_index("node")
        await LanceDB._engine.create_table(
            "mcp",
            schema=MCPVector,
            exist_ok=True,
        )
        await LanceDB.create_index("mcp")
        await LanceDB._engine.create_table(
            "mcp_tool",
            schema=MCPToolVector,
            exist_ok=True,
        )
        await LanceDB.create_index("mcp_tool")

    @staticmethod
    async def get_table(table_name: str) -> lancedb.AsyncTable:
        """
        获取LanceDB中的表

        :param str table_name: 表名
        :return: 表
        :rtype: lancedb.AsyncTable
        """
        return await LanceDB._engine.open_table(table_name)

    @staticmethod
    async def create_index(table_name: str) -> None:
        """
        创建LanceDB中表的索引；使用HNSW算法

        :param str table_name: 表名
        :return: 无
        """
        table = await LanceDB.get_table(table_name)
        await table.create_index(
            "embedding",
            config=HnswSq(),
        )
