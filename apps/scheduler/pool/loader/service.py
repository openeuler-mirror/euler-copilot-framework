"""加载配置文件夹的Service部分

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import asyncio
import uuid

import ray
from anyio import Path
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from apps.common.config import config
from apps.constants import LOGGER
from apps.entities.flow import ServiceMetadata
from apps.entities.pool import NodePool
from apps.entities.vector import NodePoolVector, ServicePoolVector
from apps.models.mongo import MongoDB
from apps.models.postgres import PostgreSQL
from apps.scheduler.openapi import reduce_openapi_spec
from apps.scheduler.pool.loader.metadata import MetadataLoader
from apps.scheduler.pool.loader.openapi import OpenAPILoader


@ray.remote
class ServiceLoader:
    """Service 加载器"""

    async def load(self, service_id: str, hashes: dict[str, str]) -> None:
        """加载单个Service"""
        service_path = Path(config["SEMANTICS_DIR"]) / "service" / service_id
        # 载入元数据
        metadata = await MetadataLoader().load_one(service_path / "metadata.yaml")
        if not isinstance(metadata, ServiceMetadata):
            err = f"元数据类型错误: {service_path / 'metadata.yaml'}"
            LOGGER.error(err)
            raise TypeError(err)
        metadata.hashes = hashes

        # 载入OpenAPI文档，获取Node列表
        openapi_loader = OpenAPILoader.remote()
        nodes = [openapi_loader.load_one.remote(service_id, yaml_path, metadata) # type: ignore[arg-type]
                async for yaml_path in (service_path / "openapi").rglob("*.yaml")]
        nodes = (await asyncio.gather(*nodes))[0]
        # 更新数据库
        await self._update_db(nodes, metadata)


    async def _update_db(self, nodes: list[NodePool], metadata: ServiceMetadata) -> None:
        """更新数据库"""
        # 更新MongoDB
        service_collection = MongoDB.get_collection("service")
        node_collection = MongoDB.get_collection("node")
        try:
            # 部分映射 ServiceMetadata 到 ServicePool, 忽略其他字段
            await service_collection.update_one({"_id": metadata.id}, {"$set": {
                "name": metadata.name,
                "description": metadata.description,
                "author": metadata.author,
                "permission": metadata.permission,
                "hashes": metadata.hashes,
            }}, upsert=True)
            for node in nodes:
                await node_collection.update_one({"_id": node.id}, {"$set": node.model_dump(exclude_none=True, by_alias=True)}, upsert=True)
        except Exception as e:
            err = f"更新MongoDB失败：{e}"
            LOGGER.error(err)
            raise RuntimeError(err) from e

        # 向量化所有数据并保存
        session = await PostgreSQL.get_session()
        service_embedding = await PostgreSQL.get_embedding([metadata.description])
        insert_stmt = insert(ServicePoolVector).values(
            id=metadata.id,
            embedding=service_embedding[0],
        ).on_conflict_do_update(
            index_elements=["id"],
            set_={"embedding": service_embedding[0]},
        )
        await session.execute(insert_stmt)

        node_descriptions = []
        for node in nodes:
            node_descriptions += [node.description]

        node_vecs = await PostgreSQL.get_embedding(node_descriptions)
        for i, data in enumerate(node_vecs):
            insert_stmt = insert(NodePoolVector).values(
                id=nodes[i].id,
                embedding=data,
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={"embedding": data},
            )
            await session.execute(insert_stmt)

        await session.commit()
        await session.aclose()

    async def save(self, service_id: str, metadata: ServiceMetadata, data: dict) -> None:
        """在文件系统上保存Service，并更新数据库"""
        # 读取 Node 信息
        openapi_spec_data = reduce_openapi_spec(data)
        nodes: list[NodePool] = []
        for endpoint in openapi_spec_data.endpoints:
            node_data = NodePool(
                _id=str(uuid.uuid4()),
                service_id=service_id,
                name=endpoint.name,
                description=endpoint.description,
                call_id="api",
            )
            nodes.append(node_data)


    async def delete(self, service_id: str) -> None:
        """删除Service，并更新数据库"""
        service_collection = MongoDB.get_collection("service")
        node_collection = MongoDB.get_collection("node")
        try:
            await service_collection.delete_one({"_id": service_id})
            await node_collection.delete_many({"service_id": service_id})
        except Exception as e:
            err = f"删除Service失败：{e}"
            LOGGER.error(err)

        session = await PostgreSQL.get_session()
        try:
            await session.execute(delete(ServicePoolVector).where(ServicePoolVector.id == service_id))
            await session.execute(delete(NodePoolVector).where(NodePoolVector.id == service_id))
            await session.commit()
        except Exception as e:
            err = f"删除数据库失败：{e}"
            LOGGER.error(err)

        await session.aclose()
