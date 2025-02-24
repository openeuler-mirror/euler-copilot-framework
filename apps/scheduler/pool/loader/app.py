"""App加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

import pathlib

import ray
from anyio import Path
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from apps.common.config import config
from apps.constants import APP_DIR, LOGGER
from apps.entities.flow import AppMetadata, MetadataType, Permission
from apps.entities.pool import AppPool
from apps.entities.vector import AppPoolVector
from apps.models.mongo import MongoDB
from apps.models.postgres import PostgreSQL
from apps.scheduler.pool.check import FileChecker
from apps.scheduler.pool.loader.metadata import MetadataLoader


@ray.remote
class AppLoader:
    """应用加载器"""

    async def load(self, app_id: str) -> None:
        """从文件系统中加载应用

        :param app_id: 应用 ID
        """
        metadata_path = Path(config["SEMANTICS_DIR"]) / APP_DIR / app_id / "metadata.yaml"
        metadata = await MetadataLoader().load_one(metadata_path)
        if not isinstance(metadata, AppMetadata):
            err = f"元数据类型错误: {metadata_path}"
            raise TypeError(err)
        await self._update_db(metadata)

    async def save(self, metadata: AppMetadata, app_id: str) -> None:
        """保存应用

        :param metadata: 应用元数据
        :param app_id: 应用 ID
        """
        await MetadataLoader().save_one(MetadataType.APP, metadata, app_id)
        await self._update_db(metadata)

    async def delete(self, app_id: str) -> None:
        """删除App，并更新数据库

        :param app_id: 应用 ID
        """
        app_collection = MongoDB.get_collection("app")
        try:
            await app_collection.delete_one({"_id": app_id})
        except Exception as e:
            err = f"删除App失败：{e}"
            LOGGER.error(err)

        session = await PostgreSQL.get_session()
        try:
            await session.execute(delete(AppPoolVector).where(AppPoolVector.id == app_id))
            await session.commit()
        except Exception as e:
            err = f"删除数据库失败：{e}"
            LOGGER.error(err)

        await session.aclose()

    async def _update_db(self, metadata: AppMetadata) -> None:
        """更新数据库"""
        hashes = FileChecker().check_one(pathlib.Path(config["SEMANTICS_DIR"]) / APP_DIR / metadata.id)
        app_collection = MongoDB.get_collection("app")
        app_pool = AppPool(
            _id=metadata.id,
            icon=metadata.icon,
            name=metadata.name,
            description=metadata.description,
            author=metadata.author,
            links=metadata.links,
            first_questions=metadata.first_questions,
            history_len=metadata.history_len,
            permission=metadata.permission if metadata.permission else Permission(),
            hashes=hashes,
        )
        if not await app_collection.find_one({"_id": metadata.id}):
            await app_collection.insert_one(jsonable_encoder(app_pool))
        else:
            await app_collection.update_one(
                {"_id": metadata.id},
                {"$set": {
                    "icon": metadata.icon,
                    "name": metadata.name,
                    "description": metadata.description,
                    "author": metadata.author,
                    "links": metadata.links,
                    "first_questions": metadata.first_questions,
                    "history_len": metadata.history_len,
                    "permission": metadata.permission if metadata.permission else Permission(),
                    "hashes": hashes,
                }},
            )
        # 向量化所有数据并保存
        session = await PostgreSQL.get_session()
        service_embedding = await PostgreSQL.get_embedding([metadata.description])
        insert_stmt = insert(AppPoolVector).values(
            id=metadata.id,
            embedding=service_embedding[0],
        ).on_conflict_do_update(
            index_elements=["id"],
            set_={"embedding": service_embedding[0]},
        )
        await session.execute(insert_stmt)
        await session.commit()
        await session.aclose()
