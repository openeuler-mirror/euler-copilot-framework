"""OpenAPI文档载入器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from pathlib import Path

import yaml

from apps.constants import LOGGER
from apps.entities.pool import NodePool
from apps.scheduler.call import API
from apps.scheduler.openapi import (
    ReducedOpenAPISpec,
    reduce_openapi_spec,
)


class OpenAPILoader:
    """OpenAPI文档载入器"""

    # 工具的参数类
    api_param_cls = API.params


    @classmethod
    def load(cls, yaml_path: Path) -> ReducedOpenAPISpec:
        """从本地磁盘加载OpenAPI文档"""
        if not yaml_path.exists():
            msg = f"File not found: {yaml_path}"
            raise FileNotFoundError(msg)

        with yaml_path.open(mode="r") as f:
            spec = yaml.safe_load(f)

        return reduce_openapi_spec(spec)


    @classmethod
    def _process_spec(cls, service_id: str, spec: ReducedOpenAPISpec) -> list[NodePool]:
        """将OpenAPI文档拆解为Node"""
        nodes = []
        for api_endpoint in spec.endpoints:
            # 组装新的Node
            node = NodePool(
                name=api_endpoint.name,
                # 此处固定Call的ID是“API”
                call_id="API",
                description=api_endpoint.description,
                service_id=service_id,
            )

            # 提取固定参数

            nodes.append(node)

        return nodes

    @classmethod
    async def load_one(cls, yaml_path: Path) -> None:
        """加载单个OpenAPI文档，可以直接指定路径"""
        try:
            spec = cls.load(yaml_path)
        except Exception as e:
            err = f"加载OpenAPI文档失败：{e}"
            LOGGER.error(msg=err)
            raise RuntimeError(err) from e
