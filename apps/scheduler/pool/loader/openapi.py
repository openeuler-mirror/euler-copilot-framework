"""OpenAPI文档载入器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from pathlib import Path
from typing import Any

import yaml

from apps.constants import LOGGER
from apps.entities.pool import NodePool
from apps.scheduler.openapi import (
    ReducedOpenAPISpec,
    reduce_openapi_spec,
)


class OpenAPILoader:
    """OpenAPI文档载入器"""

    @classmethod
    def load(cls, yaml_path: str) -> ReducedOpenAPISpec:
        """从本地磁盘加载OpenAPI文档"""
        path = Path(yaml_path)
        if not path.exists():
            msg = f"File not found: {yaml_path}"
            raise FileNotFoundError(msg)

        with path.open(mode="r") as f:
            spec = yaml.safe_load(f)

        return reduce_openapi_spec(spec)


    @classmethod
    def _process_spec(cls, spec: ReducedOpenAPISpec) -> list[NodePool]:
        """将OpenAPI文档拆解为Node"""
        


    @classmethod
    async def load_one(cls, yaml_path: str) -> None:
        """加载单个OpenAPI文档，可以直接指定路径"""
        try:
            spec = cls.load(yaml_path)
        except Exception as e:
            err = f"加载OpenAPI文档失败：{e}"
            LOGGER.error(msg=err)
            raise RuntimeError(err) from e
