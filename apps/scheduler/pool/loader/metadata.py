"""元数据加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import logging
from typing import Any, Optional, Union

import yaml
from anyio import Path
from fastapi.encoders import jsonable_encoder

from apps.common.config import config
from apps.constants import APP_DIR, SERVICE_DIR
from apps.entities.enum_var import MetadataType
from apps.entities.flow import (
    AppMetadata,
    ServiceMetadata,
)
from apps.scheduler.yaml import str_presenter

logger = logging.getLogger("ray")


class MetadataLoader:
    """元数据加载器"""

    async def load_one(self, file_path: Path) -> Optional[Union[AppMetadata, ServiceMetadata]]:
        """加载单个元数据"""
        # 检查yaml格式
        try:
            metadata_dict = yaml.safe_load(await file_path.read_text())
            # 忽略hashes和id字段，手动指定无效
            if "hashes" in metadata_dict:
                metadata_dict.pop("hashes")
            if "id" in metadata_dict:
                metadata_dict.pop("id")
            # 提取metadata的类型
            metadata_type = metadata_dict["type"]
        except Exception as e:
            err = "[MetadataLoader] metadata.yaml读取失败"
            logger.exception(err)
            raise RuntimeError(err) from e

        # 尝试匹配格式
        if metadata_type == MetadataType.APP.value:
            try:
                app_id = file_path.parent.name
                metadata = AppMetadata(id=app_id, **metadata_dict)
            except Exception as e:
                err = "[MetadataLoader] App metadata.yaml格式错误"
                logger.exception(err)
                raise RuntimeError(err) from e
        elif metadata_type == MetadataType.SERVICE.value:
            try:
                service_id = file_path.parent.name
                metadata = ServiceMetadata(id=service_id, **metadata_dict)
            except Exception as e:
                err = "[MetadataLoader] Service metadata.yaml格式错误"
                logger.exception(err)
                raise RuntimeError(err) from e
        else:
            err = f"[MetadataLoader] metadata.yaml类型错误: {metadata_type}"
            logger.error(err)
            raise RuntimeError(err)

        return metadata


    async def save_one(
        self,
        metadata_type: MetadataType,
        metadata: Union[dict[str, Any], AppMetadata, ServiceMetadata],
        resource_id: str,
    ) -> None:
        """保存单个元数据"""
        class_dict = {
            MetadataType.APP: AppMetadata,
            MetadataType.SERVICE: ServiceMetadata,
        }

        # 检查资源路径
        if metadata_type == MetadataType.APP.value:
            resource_path = Path(config["SEMANTICS_DIR"]) / APP_DIR / resource_id / "metadata.yaml"
        elif metadata_type == MetadataType.SERVICE.value:
            resource_path = Path(config["SEMANTICS_DIR"]) / SERVICE_DIR / resource_id / "metadata.yaml"
        else:
            err = f"[MetadataLoader] metadata_type类型错误: {metadata_type}"
            logger.error(err)
            raise RuntimeError(err)

        # 保存元数据
        if isinstance(metadata, dict):
            try:
                # 检查类型匹配
                metadata_class: type[Union[AppMetadata, ServiceMetadata]] = class_dict[metadata_type]
                data = metadata_class(**metadata)
            except Exception as e:
                err = "[MetadataLoader] metadata.yaml格式错误"
                logger.exception(err)
                raise RuntimeError(err) from e
        else:
            data = metadata

        # 使用UTF-8保存YAML，忽略部分乱码
        yaml.add_representer(str, str_presenter)
        yaml_dict = yaml.dump(
            jsonable_encoder(data, exclude={"hashes"}),
            allow_unicode=True,
            sort_keys=False,
        )
        await resource_path.write_text(yaml_dict)
