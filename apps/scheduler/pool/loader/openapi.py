"""OpenAPI文档载入器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import uuid

import yaml
from anyio import Path

from apps.constants import LOGGER
from apps.entities.flow import ServiceMetadata
from apps.entities.pool import NodePool
from apps.scheduler.openapi import (
    ReducedOpenAPISpec,
    reduce_openapi_spec,
)


class OpenAPILoader:
    """OpenAPI文档载入器"""

    @classmethod
    async def _read_yaml(cls, yaml_path: Path) -> ReducedOpenAPISpec:
        """从本地磁盘加载OpenAPI文档"""
        if not yaml_path.exists():
            msg = f"File not found: {yaml_path}"
            raise FileNotFoundError(msg)

        f = await yaml_path.open(mode="r")
        spec = yaml.safe_load(await f.read())
        await f.aclose()

        return reduce_openapi_spec(spec)


    @classmethod
    def _process_spec(cls, service_id: str, spec: ReducedOpenAPISpec, service_metadata: ServiceMetadata) -> list[NodePool]:
        """将OpenAPI文档拆解为Node"""
        nodes = []
        for api_endpoint in spec.endpoints:
            # 判断用户是否手动设置了ID
            node_id = api_endpoint.id if api_endpoint.id else str(uuid.uuid4())

            # 组装新的NodePool item
            node = NodePool(
                _id=node_id,
                name=api_endpoint.name,
                # 此处固定Call的ID是“API”
                call_id="API",
                description=api_endpoint.description,
                service_id=service_id,
                path="",
            )

            # 合并参数
            node.known_params = {
                "method": api_endpoint.method,
                "full_url": service_metadata.api.server + api_endpoint.uri,
            }

            nodes.append(node)

        return nodes

    @classmethod
    async def load_one(cls, yaml_folder: Path, service_metadata: ServiceMetadata) -> list[NodePool]:
        """加载单个OpenAPI文档，可以直接指定路径"""
        async for yaml_path in yaml_folder.rglob("*.yaml"):
            try:
                spec = await cls._read_yaml(yaml_path)
            except Exception as e:
                err = f"加载OpenAPI文档{yaml_path}失败：{e}"
                LOGGER.error(msg=err)
                continue

        service_id = yaml_folder.parent.name
        return cls._process_spec(service_id, spec, service_metadata)
