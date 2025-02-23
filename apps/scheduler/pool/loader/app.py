"""App加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

import pathlib

from anyio import Path
from fastapi.encoders import jsonable_encoder
from sqlalchemy.dialects.postgresql import insert

from apps.common.config import config
from apps.constants import APP_DIR
from apps.entities.flow import AppMetadata, MetadataType, Permission
from apps.entities.pool import AppPool
from apps.entities.vector import AppPoolVector
from apps.models.mongo import MongoDB
from apps.models.postgres import PostgreSQL
from apps.scheduler.pool.check import FileChecker
from apps.scheduler.pool.loader.metadata import MetadataLoader


class AppLoader:
    """应用加载器"""

    _dir_path = Path(config["SEMANTICS_DIR"])

    @classmethod
    async def load(cls, app_id: str) -> None:
        """从文件系统中加载应用

        :param app_id: 应用 ID
        """
        metadata_path = cls._dir_path / APP_DIR / app_id / "metadata.yaml"
        metadata = await MetadataLoader().load_one(metadata_path)
        if not isinstance(metadata, AppMetadata):
            err = f"元数据类型错误: {metadata_path}"
            raise TypeError(err)
        await cls._update_db(metadata)

    @classmethod
    async def save(
        cls,
        metadata_type: MetadataType,
        metadata: AppMetadata,
        app_id: str,
    ) -> None:
        """保存应用

        :param metadata_type: 元数据类型
        :param metadata: 元数据
        :param app_id: 应用 ID
        """
        await MetadataLoader().save_one(metadata_type, metadata, app_id)
        await cls._update_db(metadata)

    @classmethod
    async def _update_db(cls, metadata: AppMetadata) -> None:
        """更新数据库"""
        hashes = FileChecker().check_one(pathlib.Path(str(cls._dir_path)) / APP_DIR / metadata.id)
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
