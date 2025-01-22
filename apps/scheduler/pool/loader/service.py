"""加载配置文件夹的Service部分

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from pathlib import Path
from typing import Any

from apps.common.config import config
from apps.models.mongo import MongoDB
from apps.scheduler.pool.loader.metadata import MetadataLoader


class ServiceLoader:
    """Service 加载器"""

    _collection = MongoDB.get_collection("service")


    @classmethod
    async def load(cls, service_dir: Path) -> None:
        """加载单个Service"""
        service_path = Path(config["SERVICE_DIR"]) / "service" / service_dir
        # 载入元数据
        metadata = MetadataLoader.load(service_path / "metadata.yaml")
        # 载入OpenAPI文档
        




    @staticmethod
    async def save(cls) -> dict[str, Any]:
        """加载所有Service"""
        pass


    @staticmethod
    async def load_all(cls) -> dict[str, Any]:
        """执行Service的加载"""
        pass
