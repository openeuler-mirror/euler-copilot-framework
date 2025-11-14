# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""加载配置文件夹的Service部分"""

import asyncio
import logging
import os
import shutil

from anyio import Path
from fastapi.encoders import jsonable_encoder
from apps.common.postgres import ServicePoolVector, NodePoolVector
from apps.common.config import Config
from apps.schemas.enum_var import VectorPoolType
from apps.schemas.flow import Permission, ServiceMetadata
from apps.schemas.pool import NodePool, ServicePool
from apps.llm.embedding import Embedding
from apps.common.mongo import MongoDB
from apps.services.vector import VectorManager
from apps.scheduler.pool.check import FileChecker
from apps.scheduler.pool.loader.metadata import MetadataLoader, MetadataType
from apps.scheduler.pool.loader.openapi import OpenAPILoader

logger = logging.getLogger(__name__)
BASE_PATH = Path(Config().get_config().deploy.data_dir) / \
    "semantics" / "service"


class ServiceLoader:
    """Service 加载器"""

    async def load(self, service_id: str, hashes: dict[str, str]) -> None:
        """加载单个Service"""
        service_path = BASE_PATH / service_id
        # 载入元数据
        if not os.path.exists(service_path / "metadata.yaml"):
            logger.error("[ServiceLoader] Service %s 的元数据不存在", service_id)
            return
        metadata = await MetadataLoader().load_one(service_path / "metadata.yaml")
        if not isinstance(metadata, ServiceMetadata):
            err = f"[ServiceLoader] 元数据类型错误: {service_path}/metadata.yaml"
            logger.error(err)
            raise TypeError(err)
        metadata.hashes = hashes

        # 载入OpenAPI文档，获取Node列表
        try:
            nodes: list[NodePool] = []
            async for yaml_path in (service_path / "openapi").rglob("*.yaml"):
                nodes.extend(await OpenAPILoader().load_one(service_id, yaml_path, metadata.api.server))
        except Exception:
            logger.exception("[ServiceLoader] 服务 %s 文件损坏", service_id)
            return
        # 更新数据库
        await self._update_db(nodes, metadata)

    async def save(self, service_id: str, metadata: ServiceMetadata, data: dict) -> None:
        """在文件系统上保存Service，并更新数据库"""
        service_path = BASE_PATH / service_id
        # 创建文件夹
        if not await service_path.exists():
            await service_path.mkdir(parents=True, exist_ok=True)
        if not await (service_path / "openapi").exists():
            await (service_path / "openapi").mkdir(parents=True, exist_ok=True)
        openapi_path = service_path / "openapi" / "api.yaml"
        # 保存元数据
        await MetadataLoader().save_one(MetadataType.SERVICE, metadata, service_id)
        # 保存 OpenAPI 文档
        await OpenAPILoader().save_one(openapi_path, data)
        # 重新载入
        file_checker = FileChecker()
        await file_checker.diff_one(service_path)
        await self.load(service_id, file_checker.hashes[f"service/{service_id}"])

    async def delete(self, service_id: str, *, is_reload: bool = False) -> None:
        """删除Service，并更新数据库"""
        service_collection = MongoDB.get_collection("service")
        node_collection = MongoDB.get_collection("node")
        try:
            await service_collection.delete_one({"_id": service_id})
            await node_collection.delete_many({"service_id": service_id})
        except Exception:
            logger.exception("[ServiceLoader] 删除Service失败")

        await VectorManager.delete_vectors(
            vector_type=VectorPoolType.SERVICE,
            ids=[service_id],
        )
        await VectorManager.delete_call_vectors_by_service_ids(
            service_ids=[service_id],
        )

        if not is_reload:
            path = BASE_PATH / service_id
            if await path.exists():
                shutil.rmtree(path)

    async def _update_db(self, nodes: list[NodePool], metadata: ServiceMetadata) -> None:  # noqa: C901, PLR0912, PLR0915
        """更新数据库"""
        if not metadata.hashes:
            err = f"[ServiceLoader] 服务 {metadata.id} 的哈希值为空"
            logger.error(err)
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
                await node_collection.update_one({"_id": node.id}, {"$set": jsonable_encoder(node)}, upsert=True)
        except Exception as e:
            err = f"[ServiceLoader] 更新 MongoDB 失败：{e}"
            logger.exception(err)
            raise RuntimeError(err) from e

        # 向量化所有数据并保存
        await VectorManager.delete_vectors(
            vector_type=VectorPoolType.SERVICE,
            ids=[metadata.id],
        )
        await VectorManager.delete_call_vectors_by_service_ids(
            service_ids=[metadata.id],
        )

        # 进行向量化，更新LanceDB
        service_vecs = await Embedding.get_embedding([metadata.description])
        service_vector_pool_entity = ServicePoolVector(
            id=metadata.id,
            embedding=service_vecs[0],
        )
        await VectorManager.add_vector(service_vector_pool_entity)

        node_descriptions = []
        for node in nodes:
            node_descriptions += [node.description]

        node_vecs = await Embedding.get_embedding(node_descriptions)
        node_vector_pool_entities = []
        for i, vec in enumerate(node_vecs):
            node_vector_pool_entities.append(
                NodePoolVector(
                    id=nodes[i].id,
                    service_id=metadata.id,
                    embedding=vec,
                )
            )
        BATCH_SIZE = 1024
        for i in range(0, len(node_vector_pool_entities), BATCH_SIZE):
            batch = node_vector_pool_entities[i:i + BATCH_SIZE]
            await VectorManager.add_vectors(batch)
