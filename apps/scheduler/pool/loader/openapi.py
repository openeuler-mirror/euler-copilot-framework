"""OpenAPI文档载入器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

import uuid
from typing import Any

import ray
import yaml
from anyio import Path

from apps.constants import LOGGER
from apps.entities.enum_var import ContentType, HTTPMethod
from apps.entities.flow import ServiceMetadata
from apps.entities.node import APINode, APINodeInput, APINodeOutput
from apps.scheduler.openapi import (
    ReducedOpenAPIEndpoint,
    ReducedOpenAPISpec,
    reduce_openapi_spec,
)


@ray.remote
class OpenAPILoader:
    """OpenAPI文档载入器"""

    async def _read_yaml(self, yaml_path: Path) -> ReducedOpenAPISpec:
        """从本地磁盘加载OpenAPI文档"""
        if not await yaml_path.exists():
            msg = f"File not found: {yaml_path}"
            raise FileNotFoundError(msg)

        f = await yaml_path.open(mode="r")
        spec = yaml.safe_load(await f.read())
        await f.aclose()

        return reduce_openapi_spec(spec)

    async def parameters_to_spec(self, raw_schema: list[dict[str, Any]]) -> dict[str, Any]:
        """将OpenAPI中GET接口List形式的请求体Spec转换为JSON Schema"""
        schema = {
            "type": "object",
            "required": [],
            "properties": {},
        }
        for item in raw_schema:
            if item["required"]:
                schema["required"].append(item["name"])
            schema["properties"][item["name"]] = {}
            schema["properties"][item["name"]]["description"] = item["description"]
            for key, val in item["schema"].items():
                schema["properties"][item["name"]][key] = val
        return schema

    async def _get_api_data(
        self,
        spec: ReducedOpenAPIEndpoint,
        service_metadata: ServiceMetadata,
    ) -> tuple[APINodeInput, APINodeOutput, dict[str, Any]]:
        """从OpenAPI文档中获取API数据"""
        try:
            method = HTTPMethod[spec.method.upper()]
        except KeyError as e:
            err = f"HTTP方法{spec.method}不支持。"
            LOGGER.error(msg=err)
            raise RuntimeError(err) from e

        url = service_metadata.api.server.rstrip("/") + spec.uri
        known_params = {}

        if method in (HTTPMethod.POST, HTTPMethod.PUT, HTTPMethod.PATCH):
            body_spec = spec.spec["requestBody"]["content"]

            # 从body_spec中找到第一个支持的content type
            content_type = next(
                (ct for ct in ContentType if ct.value in body_spec),
                None,
            )
            known_params["content_type"]=content_type
            if content_type is None:
                err = f"接口{spec.name}的Content-Type不支持"
                LOGGER.error(msg=err)
                raise RuntimeError(err)

        try:
            inp = APINodeInput(
                param_schema=await self.parameters_to_spec(spec.spec["parameters"])
                if "parameters" in spec.spec
                else None,
                body_schema=spec.spec["requestBody"]["content"][content_type]["schema"]
                if "requestBody" in spec.spec
                else None,
            )
        except KeyError:
            err = f"接口{spec.name}请求体定义错误"
            LOGGER.error(msg=err)

        try:
            out = APINodeOutput(
                resp_schema=spec.spec["responses"]["200"]["content"]["application/json"]["schema"],
            )
        except KeyError:
            err = f"接口{spec.name}不存在响应体定义"
            LOGGER.error(msg=err)
            out = APINodeOutput()

        known_params = {
            "url": url,
            "method": method,
        }

        return inp, out, known_params

    async def _process_spec(
        self,
        service_id: str,
        yaml_filename: str,
        spec: ReducedOpenAPISpec,
        service_metadata: ServiceMetadata,
    ) -> list[APINode]:
        """将OpenAPI文档拆解为Node"""
        nodes = []
        for api_endpoint in spec.endpoints:
            # 组装新的NodePool item
            node = APINode(
                _id=str(uuid.uuid4()),
                name=api_endpoint.name,
                # 此处固定Call的ID是"API"
                call_id="API",
                description=api_endpoint.description,
                service_id=service_id,
                annotation=f"openapi::{yaml_filename}",
            )

            # 合并参数
            node.override_input, node.override_output, node.known_params = await self._get_api_data(
                api_endpoint,
                service_metadata,
            )
            nodes.append(node)
        return nodes

    async def load_one(self, service_id: str, yaml_path: Path, service_metadata: ServiceMetadata) -> list[APINode]:
        """加载单个OpenAPI文档，可以直接指定路径"""
        try:
            spec = await self._read_yaml(yaml_path)
        except Exception as e:
            err = f"加载OpenAPI文档{yaml_path}失败：{e}"
            LOGGER.error(msg=err)
            raise RuntimeError(err) from e

        yaml_filename = yaml_path.name
        try:
            return await self._process_spec(service_id, yaml_filename, spec, service_metadata)
        except Exception as e:
            err = f"处理OpenAPI文档{yaml_filename}失败：{e}"
            LOGGER.error(msg=err)
            raise RuntimeError(err) from e

    async def save_one(self, yaml_path: Path, yaml_dict: dict[str, Any]) -> None:
        """保存单个OpenAPI文档"""
        """在文件系统上保存Service，并更新数据库"""

        try:
            yaml_data = yaml.safe_dump(yaml_dict)
            await yaml_path.write_text(yaml_data)
        except Exception as e:
            if await yaml_path.exists():
                await yaml_path.unlink()
            err = f"保存OpenAPI文档{yaml_path}失败：{e}"
            LOGGER.error(msg=err)
            raise RuntimeError(err) from e
