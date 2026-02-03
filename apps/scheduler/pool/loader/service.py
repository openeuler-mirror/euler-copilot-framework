# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""加载配置文件夹的Service部分；下属于Pool，单例"""

import logging
import shutil
import uuid

from anyio import Path
from sqlalchemy import delete, inspect, select

from apps.common.config import config
from apps.common.postgres import postgres
from apps.llm import embedding
from apps.models import (
    NodeInfo,
    PermissionType,
    Service,
    ServiceACL,
    ServiceHashes,
)
from apps.scheduler.pool.check import FileChecker
from apps.schemas.flow import ServiceMetadata

from .metadata import MetadataLoader, MetadataType
from .openapi import OpenAPILoader

logger = logging.getLogger(__name__)
BASE_PATH = Path(config.deploy.data_dir) / "semantics" / "service"


async def _table_exists(table_name: str) -> bool:
    """检查表是否存在"""
    async with postgres.engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table(table_name),
        )


class ServiceLoader:
    """Service 加载器"""

    @staticmethod
    async def _load_all_services() -> list[tuple[Service, list[NodeInfo]]]:
        """从数据库加载所有服务和对应的节点"""
        async with postgres.session() as session:
            # 查询所有服务
            services_query = select(Service)
            services = list((await session.scalars(services_query)).all())

            # 为每个服务查询对应的节点
            service_nodes = []
            for service in services:
                nodes_query = select(NodeInfo).where(NodeInfo.serviceId == service.id)
                nodes = list((await session.scalars(nodes_query)).all())
                service_nodes.append((service, nodes))

            return service_nodes

    @staticmethod
    async def load(service_id: uuid.UUID, hashes: dict[str, str]) -> None:
        """加载单个Service"""
        service_path = BASE_PATH / str(service_id)
        # 载入元数据
        if not await (service_path / "metadata.yaml").exists():
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
            nodes: list[NodeInfo] = []
            async for yaml_path in (service_path / "openapi").rglob("*.yaml"):
                nodes.extend(await OpenAPILoader().load_one(service_id, yaml_path, metadata.api.server))
        except Exception:
            logger.exception("[ServiceLoader] 服务 %s 文件损坏", service_id)
            return
        # 更新数据库
        await ServiceLoader._update_db(nodes, metadata)


    @staticmethod
    async def save(service_id: uuid.UUID, metadata: ServiceMetadata, data: dict) -> None:
        """在文件系统上保存Service，并更新数据库"""
        service_path = BASE_PATH / str(service_id)
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
        await ServiceLoader.load(service_id, file_checker.hashes[f"service/{service_id}"])


    @staticmethod
    async def delete(service_id: uuid.UUID, *, is_reload: bool = False) -> None:
        """删除Service，并更新数据库"""
        async with postgres.session() as session:
            await session.execute(delete(NodeInfo).where(NodeInfo.serviceId == service_id))
            await session.execute(delete(ServiceACL).where(ServiceACL.serviceId == service_id))
            await session.execute(delete(ServiceHashes).where(ServiceHashes.serviceId == service_id))

            if embedding.ServicePoolVector is not None:
                await session.execute(
                    delete(embedding.ServicePoolVector).where(embedding.ServicePoolVector.id == service_id),
                )
            if embedding.NodePoolVector is not None:
                await session.execute(
                    delete(
                        embedding.NodePoolVector,
                    ).where(embedding.NodePoolVector.serviceId == service_id),
                )
            await session.execute(delete(Service).where(Service.id == service_id))
            await session.commit()

        if not is_reload:
            path = BASE_PATH / str(service_id)
            if await path.exists():
                shutil.rmtree(path)


    @staticmethod
    async def _update_db(nodes: list[NodeInfo], metadata: ServiceMetadata) -> None:
        """更新数据库"""
        if not metadata.hashes:
            err = f"[ServiceLoader] 服务 {metadata.id} 的哈希值为空"
            logger.error(err)
            raise ValueError(err)

        # 更新数据库
        async with postgres.session() as session:
            # 删除旧的数据
            await session.execute(delete(Service).where(Service.id == metadata.id))
            await session.execute(delete(NodeInfo).where(NodeInfo.serviceId == metadata.id))
            await session.execute(delete(ServiceHashes).where(ServiceHashes.serviceId == metadata.id))

            # 插入新的数据
            service_data = Service(
                id=metadata.id,
                name=metadata.name,
                description=metadata.description,
                authorId=metadata.author,
                permission=PermissionType.PRIVATE,
            )
            session.add(service_data)

            # 立即执行插入Service的SQL，让数据库能查到它，解决外键检查问题
            await session.flush()

            for node in nodes:
                session.add(node)

            # 保存哈希值
            for file_path, hash_value in metadata.hashes.items():
                hash_data = ServiceHashes(
                    serviceId=metadata.id,
                    filePath=file_path,
                    hash=hash_value,
                )
                session.add(hash_data)

            await session.commit()

    @staticmethod
    async def set_vector() -> None:
        """将所有服务和节点的向量化数据存入数据库"""
        service_nodes = await ServiceLoader._load_all_services()

        # 为每个服务调用现有的update_vector方法
        for service, nodes in service_nodes:
            await ServiceLoader._update_vector(
                nodes,
                service.id,
                service.description,
            )

    @staticmethod
    async def _update_vector(
        nodes: list[NodeInfo],
        service_id: uuid.UUID,
        service_description: str,
    ) -> None:
        """更新向量数据"""
        # 检查 embedding 是否已初始化
        if embedding.ServicePoolVector is None or embedding.NodePoolVector is None:
            logger.warning(
                "[ServiceLoader] Embedding 未初始化,跳过向量数据更新",
            )
            return

        # 检查表是否存在
        if not await _table_exists(embedding.ServicePoolVector.__tablename__):
            logger.warning(
                "[ServiceLoader] 表 %s 不存在,跳过向量数据更新",
                embedding.ServicePoolVector.__tablename__,
            )
            return

        service_vecs = await embedding.get_embedding([service_description])
        node_descriptions = []
        for node in nodes:
            node_descriptions += [node.description]
        node_vecs = await embedding.get_embedding(node_descriptions)

        async with postgres.session() as session:
            # 删除旧数据
            await session.execute(
                delete(embedding.ServicePoolVector).where(embedding.ServicePoolVector.id == service_id),
            )
            await session.execute(
                delete(embedding.NodePoolVector).where(embedding.NodePoolVector.serviceId == service_id),
            )
            # 插入新数据
            session.add(embedding.ServicePoolVector(
                id=service_id,
                embedding=service_vecs[0],
            ))
            for vec in node_vecs:
                node_data = embedding.NodePoolVector(
                    id=node.id,
                    serviceId=service_id,
                    embedding=vec,
                )
                session.add(node_data)
            await session.commit()
