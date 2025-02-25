"""加载配置文件夹的Service部分

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

import asyncio

import ray
from anyio import Path
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from apps.common.config import config
from apps.constants import LOGGER, SERVICE_DIR
from apps.entities.flow import Permission, ServiceMetadata
from apps.entities.pool import NodePool, ServicePool
from apps.entities.vector import NodePoolVector, ServicePoolVector
from apps.models.mongo import MongoDB
from apps.models.postgres import PostgreSQL
from apps.scheduler.pool.check import FileChecker
from apps.scheduler.pool.loader.metadata import MetadataLoader, MetadataType
from apps.scheduler.pool.loader.openapi import OpenAPILoader


@ray.remote
class ServiceLoader:
    """Service 加载器"""

    async def load(self, service_id: str, hashes: dict[str, str]) -> None:
        """加载单个Service"""
        service_path = Path(config["SEMANTICS_DIR"]) / SERVICE_DIR / service_id
        # 载入元数据
        metadata = await MetadataLoader().load_one(service_path / "metadata.yaml")
        if not isinstance(metadata, ServiceMetadata):
            err = f"[ServiceLoader] 元数据类型错误: {service_path / 'metadata.yaml'}"
            LOGGER.error(err)
            raise TypeError(err)
        metadata.hashes = hashes

        # 载入OpenAPI文档，获取Node列表
        openapi_loader = OpenAPILoader.remote()
        try:
            nodes = [
                openapi_loader.load_one.remote(service_id, yaml_path, metadata)  # type: ignore[arg-type]
                async for yaml_path in (service_path / "openapi").rglob("*.yaml")
            ]
        except Exception as e:
            LOGGER.error(f"[ServiceLoader] 服务 {service_id} 文件损坏: {e}")
            return
        try:
            data = await asyncio.gather(*nodes)
            nodes = data[0]
        except Exception as e:
            LOGGER.error(f"[ServiceLoader] 服务 {service_id} 获取Node列表失败: {e}")
            return
        # 更新数据库
        nodes = [NodePool(**node.model_dump(exclude_none=True, by_alias=True)) for node in nodes]
        await self._update_db(nodes, metadata)

    async def save(self, service_id: str, metadata: ServiceMetadata, data: dict) -> None:
        """在文件系统上保存Service，并更新数据库"""
        service_path = Path(config["SEMANTICS_DIR"]) / SERVICE_DIR / service_id
        # 创建文件夹
        if not service_path.exists():
            await service_path.mkdir(parents=True, exist_ok=True)
        if not (service_path / "openapi").exists():
            await (service_path / "openapi").mkdir(parents=True, exist_ok=True)
        openapi_path = service_path / "openapi" / "api.yaml"
        # 保存元数据
        await MetadataLoader().save_one(MetadataType.SERVICE, metadata, service_id)
        # 保存 OpenAPI 文档
        openapi_loader = OpenAPILoader.remote()
        await openapi_loader.save_one.remote(openapi_path, data)  # type: ignore[arg-type]
        ray.kill(openapi_loader)
        # 重新载入
        file_checker = FileChecker()
        await file_checker.diff_one(service_path)
        await self.load(service_id, file_checker.hashes[f"{SERVICE_DIR}/{service_id}"])

    async def delete(self, service_id: str) -> None:
        """删除Service，并更新数据库"""
        service_collection = MongoDB.get_collection("service")
        node_collection = MongoDB.get_collection("node")
        try:
            await service_collection.delete_one({"_id": service_id})
            await node_collection.delete_many({"service_id": service_id})
        except Exception as e:
            err = f"[ServiceLoader] 删除Service失败：{e}"
            LOGGER.error(err)

        session = await PostgreSQL.get_session()
        try:
            await session.execute(delete(ServicePoolVector).where(ServicePoolVector.id == service_id))
            await session.execute(delete(NodePoolVector).where(NodePoolVector.id == service_id))
            await session.commit()
        except Exception as e:
            err = f"[ServiceLoader] 删除数据库失败：{e}"
            LOGGER.error(err)

        await session.aclose()

    async def _update_db(self, nodes: list[NodePool], metadata: ServiceMetadata) -> None:
        """更新数据库"""
        if not metadata.hashes:
            err = f"[ServiceLoader] 服务 {metadata.id} 的哈希值为空"
            LOGGER.error(err)
            raise ValueError(err)
        # 更新MongoDB
        service_collection = MongoDB.get_collection("service")
        node_collection = MongoDB.get_collection("node")
        try:
            # 先删除旧的节点
            await node_collection.delete_many({"service_id": metadata.id})
            # 插入或更新 Service
            await service_collection.update_one(
                {"_id": metadata.id},
                {
                    "$set": jsonable_encoder(
                        ServicePool(
                            _id=metadata.id,
                            name=metadata.name,
                            description=metadata.description,
                            author=metadata.author,
                            permission=metadata.permission if metadata.permission else Permission(),
                            hashes=metadata.hashes,
                        ),
                    ),
                },
                upsert=True,
            )
            for node in nodes:
                await node_collection.insert_one(jsonable_encoder(node))
        except Exception as e:
            err = f"[ServiceLoader] 更新 MongoDB 失败：{e}"
            LOGGER.error(err)
            raise RuntimeError(err) from e

        # 向量化所有数据并保存
        session = await PostgreSQL.get_session()
        service_embedding = await PostgreSQL.get_embedding([metadata.description])
        insert_stmt = (
            insert(ServicePoolVector)
            .values(
                id=metadata.id,
                embedding=service_embedding[0],
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={"embedding": service_embedding[0]},
            )
        )
        await session.execute(insert_stmt)

        node_descriptions = []
        for node in nodes:
            node_descriptions += [node.description]

        node_vecs = await PostgreSQL.get_embedding(node_descriptions)
        for i, data in enumerate(node_vecs):
            insert_stmt = (
                insert(NodePoolVector)
                .values(
                    id=nodes[i].id,
                    embedding=data,
                )
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={"embedding": data},
                )
            )
            await session.execute(insert_stmt)

        await session.commit()
        await session.aclose()
