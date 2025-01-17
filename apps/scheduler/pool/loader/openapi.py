"""OpenAPI文档载入器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from pathlib import Path
from typing import Any

import yaml

from apps.constants import LOGGER
from apps.scheduler.openapi import (
    ReducedOpenAPISpec,
    reduce_openapi_spec,
)
from apps.scheduler.pool.util import get_bytes_hash


class OpenAPILoader:
    """OpenAPI文档载入器"""

    @staticmethod
    def _load_spec(yaml_path: str) -> tuple[str, ReducedOpenAPISpec]:
        """从本地磁盘加载OpenAPI文档"""
        path = Path(yaml_path)
        if not path.exists():
            msg = f"File not found: {yaml_path}"
            raise FileNotFoundError(msg)

        with path.open(mode="rb") as f:
            content = f.read()
            hash_value = get_bytes_hash(content)
            spec = yaml.safe_load(content)
        return hash_value, reduce_openapi_spec(spec)


    @classmethod
    def _process_spec(cls, spec: ReducedOpenAPISpec) -> dict[str, Any]:
        """处理OpenAPI文档"""
        pass


    @staticmethod
    async def load_one(yaml_path: str) -> None:
        """加载单个OpenAPI文档，可以直接指定路径"""
        try:
            hash_val, spec_raw = OpenAPILoader._load_spec(yaml_path)
        except Exception as e:
            err = f"加载OpenAPI文档失败：{e}"
            LOGGER.error(msg=err)
            raise RuntimeError(err) from e



    @classmethod
    def load(cls) -> ReducedOpenAPISpec:
        """执行OpenAPI文档的加载"""
        pass

