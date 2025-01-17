"""元数据加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from pathlib import Path
from typing import Any, Union

import yaml

from apps.constants import LOGGER
from apps.entities.enum_var import MetadataType
from apps.entities.flow import (
    AppMetadata,
    ServiceMetadata,
)


class MetadataLoader:
    """元数据加载器"""

    @staticmethod
    async def load(file_path: Path) -> Union[AppMetadata, ServiceMetadata]:
        """检查metadata.yaml是否正确"""
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


    @staticmethod
    async def save(metadata: dict[str, Any], file_path: Path) -> None:
        """将元数据保存到文件"""
        pass
