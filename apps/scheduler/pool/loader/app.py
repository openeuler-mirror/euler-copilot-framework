"""App加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

from anyio import Path

from apps.common.config import config
from apps.entities.flow import MetadataType
from apps.scheduler.pool.loader.metadata import MetadataLoader


class AppLoader:
    """应用加载器"""

    @classmethod
    async def load(cls, app_dir: str) -> None:
        """从文件系统中加载应用

        :param app_dir: 应用目录
        """
        path = Path(config["SEMANTICS_DIR"]) / app_dir
        metadata = await MetadataLoader.load(path / "metadata.yaml")


    @classmethod
    async def save(cls, metadata_type: MetadataType, metadata: dict[str, Any], resource_id: str) -> None:
        """保存应用"""
        await MetadataLoader.save(metadata_type, metadata, resource_id)
