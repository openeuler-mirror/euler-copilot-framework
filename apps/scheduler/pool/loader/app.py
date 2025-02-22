"""App加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from hashlib import sha256
from typing import Any

from anyio import Path

from apps.common.config import config
from apps.entities.flow import AppMetadata, MetadataType
from apps.entities.pool import AppPool
from apps.models.mongo import MongoDB
from apps.scheduler.pool.loader.metadata import MetadataLoader


class AppLoader:
    """应用加载器"""

    _dir_path = Path(config["SEMANTICS_DIR"])

    @classmethod
    async def load_one(cls, app_id: str) -> None:
        """从文件系统中加载应用

        :param app_id: 应用 ID
        """
        metadata_path = cls._dir_path / "app" / app_id / "metadata.yaml"
        metadata = await MetadataLoader().load_one(metadata_path)
        if not isinstance(metadata, AppMetadata):
            err = f"元数据类型错误: {metadata_path}"
            raise TypeError(err)
        metadata_hash = sha256(await metadata_path.read_bytes()).hexdigest()
        hashes = { str(metadata_path.relative_to(cls._dir_path)): metadata_hash }
        app_collection = MongoDB.get_collection("app")
        app_pool = AppPool(
            _id=metadata.id,
            icon=metadata.icon,
            name=metadata.name,
            description=metadata.description,
            author=metadata.author,
            history_len=metadata.history_len,
            hashes=hashes,
        )
        if not await app_collection.find_one({"_id": metadata.id}):
            await app_collection.insert_one(app_pool.model_dump(exclude_none=True, by_alias=True))
        else:
            await app_collection.update_one(
                {"_id": metadata.id},
                {"$set": app_pool.model_dump(exclude_none=True, by_alias=True)},
            )


    @classmethod
    async def save_one(cls, metadata_type: MetadataType, metadata: dict[str, Any], app_id: str) -> dict[str, str]:
        """保存应用

        :param metadata_type: 元数据类型
        :param metadata: 元数据
        :param app_id: 应用 ID

        :return: 文件路径和哈希值
        """
        await MetadataLoader().save_one(metadata_type, metadata, app_id)
        metadata_path = cls._dir_path / "app" / app_id / "metadata.yaml"
        metadata_hash = sha256(await metadata_path.read_bytes()).hexdigest()
        return { str(metadata_path.relative_to(cls._dir_path)): metadata_hash }
