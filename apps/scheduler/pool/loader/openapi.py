"""OpenAPI文档载入器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from pathlib import Path
from typing import Any

import yaml

from apps.scheduler.openapi import ReducedOpenAPISpec, reduce_openapi_spec
from apps.scheduler.pool.util import get_bytes_hash


class OpenAPILoader:
    """OpenAPI文档载入器"""

    @classmethod
    def load_from_disk(cls, yaml_path: str) -> tuple[str, ReducedOpenAPISpec]:
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
    def load_from_minio(cls, yaml_path: str) -> tuple[str, ReducedOpenAPISpec]:
        """从MinIO加载OpenAPI文档"""
        pass

    @classmethod
    def load(cls) -> ReducedOpenAPISpec:
        """执行OpenAPI文档的加载"""
        pass

    @classmethod
    def process(cls, spec: ReducedOpenAPISpec) -> dict[str, Any]:
        """处理OpenAPI文档"""
        pass

