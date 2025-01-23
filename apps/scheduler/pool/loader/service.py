"""加载配置文件夹的Service部分

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

from anyio import Path

from apps.common.config import config
from apps.entities.vector import NodeVector, ServiceVector
from apps.models.mongo import MongoDB
from apps.models.postgres import PostgreSQL
from apps.scheduler.pool.loader.metadata import MetadataLoader
from apps.scheduler.pool.loader.openapi import OpenAPILoader


class ServiceLoader:
    """Service 加载器"""

    _collection = MongoDB.get_collection("service")


    @classmethod
    async def load(cls, service_dir: Path) -> None:
        """加载单个Service"""
        service_path = Path(config["SERVICE_DIR"]) / "service" / service_dir
        # 载入元数据
        metadata = await MetadataLoader.load(service_path / "metadata.yaml")
        # 载入OpenAPI文档，获取Node列表
        nodes = await OpenAPILoader.load_one(service_path / "openapi.yaml")

        # 向量化所有数据
        session = await PostgreSQL.get_session()
        service_vec = ServiceVector(
            _id=metadata.id,
            embedding=PostgreSQL.get_embedding([metadata.description]),
        )
        session.add(service_vec)

        node_descriptions = []
        for node in nodes:
            node_descriptions += [node.description]

        node_vecs = await PostgreSQL.get_embedding(node_descriptions)
        for i, data in enumerate(node_vecs):
            node_vec = NodeVector(
                _id=nodes[i].id,
                embedding=data,
            )
            session.add(node_vec)

        await session.commit()






    @staticmethod
    async def save(cls) -> dict[str, Any]:
        """加载所有Service"""
        pass


    @staticmethod
    async def load_all(cls) -> dict[str, Any]:
        """执行Service的加载"""
        pass
