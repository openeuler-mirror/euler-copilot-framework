"""元数据加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from pathlib import Path

import yaml

from apps.constants import LOGGER
from apps.entities.flow import Metadata


class MetadataLoader:
    """元数据加载器"""

    @staticmethod
    def check_metadata(dir: Path) -> bool:
        """检查metadata.yaml是否正确"""
        # 检查yaml格式
        try:
            metadata = yaml.safe_load(Path(dir, "metadata.yaml").read_text())
        except Exception as e:
            LOGGER.error("metadata.yaml读取失败: %s", e)
            return False
        
        

    @classmethod
    async def load(cls) -> None:
        """执行元数据加载"""
        pass
