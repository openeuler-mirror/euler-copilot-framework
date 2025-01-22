"""元数据加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from pathlib import Path
from typing import Any, Union

import yaml

from apps.common.config import config
from apps.constants import LOGGER
from apps.entities.enum_var import MetadataType
from apps.entities.flow import (
    AppMetadata,
    ServiceMetadata,
)


class MetadataLoader:
    """元数据加载器"""

    @classmethod
    async def load(cls, file_path: Path) -> Union[AppMetadata, ServiceMetadata]:
        """加载【单个】元数据"""
        # 检查yaml格式
        try:
            metadata_dict = yaml.safe_load(file_path.read_text())
            metadata_type = metadata_dict["type"]
        except Exception as e:
            err = f"metadata.yaml读取失败: {e}"
            LOGGER.error(err)
            raise RuntimeError(err) from e

        if metadata_type not in MetadataType:
            err = f"metadata.yaml类型错误: {metadata_type}"
            LOGGER.error(err)
            raise RuntimeError(err)

        # 尝试匹配格式
        try:
            if metadata_type == MetadataType.APP:
                metadata = AppMetadata(**metadata_dict)
            elif metadata_type == MetadataType.SERVICE:
                metadata = ServiceMetadata(**metadata_dict)
        except Exception as e:
            err = f"metadata.yaml格式错误: {e}"
            LOGGER.error(err)
            raise RuntimeError(err) from e

        return metadata


    @classmethod
    async def save(cls, metadata_type: MetadataType, metadata: dict[str, Any], resource_id: str) -> None:
        """保存【单个】元数据"""
        class_dict = {
            MetadataType.APP: AppMetadata,
            MetadataType.SERVICE: ServiceMetadata,
        }

        # 检查资源路径
        if metadata_type == MetadataType.APP:
            resource_path = Path(config["SERVICE_DIR"]) / "app" / resource_id / "metadata.yaml"
        elif metadata_type == MetadataType.SERVICE:
            resource_path = Path(config["SERVICE_DIR"]) / "service" / resource_id / "metadata.yaml"

        # 保存元数据
        try:
            metadata_class: type[Union[AppMetadata, ServiceMetadata]] = class_dict[metadata_type]
            data = metadata_class(**metadata)
        except Exception as e:
            err = f"metadata.yaml格式错误: {e}"
            LOGGER.error(err)
            raise RuntimeError(err) from e

        yaml_data = data.model_dump(by_alias=True, exclude_none=True)
        resource_path.write_text(yaml.safe_dump(yaml_data))
