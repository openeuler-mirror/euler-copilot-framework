# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""OpenAPI文档载入器"""

import logging
from hashlib import shake_128
from typing import Any

import yaml
from anyio import Path

from apps.scheduler.openapi import (
    ReducedOpenAPIEndpoint,
    ReducedOpenAPISpec,
    reduce_openapi_spec,
)
from apps.scheduler.slot.slot import Slot
from apps.scheduler.util import yaml_str_presenter
from apps.schemas.enum_var import ContentType, HTTPMethod
from apps.schemas.node import APINode, APINodeInput, APINodeOutput
from apps.schemas.pool import NodePool

logger = logging.getLogger(__name__)


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
        server: str,
    ) -> tuple[APINodeInput, APINodeOutput, dict[str, Any]]:
        """从OpenAPI文档中获取API数据"""
        try:
            method = HTTPMethod[spec.method.upper()]
        except KeyError as e:
            err = f"[OpenAPILoader] HTTP方法“{spec.method}”不支持。"
            logger.warning(err)
            raise ValueError(err) from e

        url = server.rstrip("/") + spec.uri
        known_params = {}
        content_type = None

        if method in (HTTPMethod.POST, HTTPMethod.PUT, HTTPMethod.PATCH):
            body_spec = spec.spec["requestBody"]["content"]

            # 从body_spec中找到第一个支持的content type
            content_type = next(
                (ct for ct in ContentType if ct.value in body_spec),
                None,
            )
            known_params["content_type"] = content_type
            if content_type is None:
                err = f"[OpenAPILoader] 接口“{spec.name}”的Content-Type不支持"
                logger.warning(err)
                raise ValueError(err)

        try:
            body_schema = None
            if "requestBody" in spec.spec and content_type is not None:
                body_schema = spec.spec["requestBody"]["content"][content_type]["schema"]

            inp = APINodeInput(
                query=await self.parameters_to_spec(spec.spec["parameters"])
                if "parameters" in spec.spec
                else None,
                body=body_schema,
            )
        except KeyError as e:
            err = f"[OpenAPILoader] 接口“{spec.name}”请求体定义错误: {e!s}"
            logger.warning(err)
            raise ValueError(err) from e

        # 将数据转为已知JSON
        known_body = Slot(inp.body).create_empty_slot() if inp.body else {}
        known_query = Slot(inp.query).create_empty_slot() if inp.query else {}

        try:
            out = APINodeOutput(
                result=spec.spec["responses"]["content"]["application/json"]["schema"],
            )
        except KeyError as e:
            err = f"[OpenAPILoader] 接口“{spec.name}”不存在响应体定义: {e!s}"
            logger.warning(err)
            raise ValueError(err) from e

        known_params = {
            "url": url,
            "method": method,
            "content_type": content_type,
            "body": known_body,
            "query": known_query,
        }

        return inp, out, known_params

    async def _process_spec(
        self,
        service_id: str,
        yaml_filename: str,
        spec: ReducedOpenAPISpec,
        server: str,
    ) -> list[APINode]:
        """将OpenAPI文档拆解为Node"""
        nodes = []
        for api_endpoint in spec.endpoints:
            # 通过算法生成唯一的标识符
            identifier = shake_128(f"{service_id}/{yaml_filename}/{api_endpoint.name}".encode()).hexdigest(16)
            # 组装新的NodePool item
            node = APINode(
                _id=identifier,
                name=api_endpoint.name,
                # 此处固定Call的ID是"API"
                call_id="API",
                description=api_endpoint.description,
                service_id=service_id,
            )

            # 合并参数
            node.override_input, node.override_output, node.known_params = await self._get_api_data(
                api_endpoint,
                server,
            )
            nodes.append(node)
        return nodes


    async def load_dict(
        self,
        yaml_dict: dict[str, Any],
    ) -> ReducedOpenAPISpec:
        """加载字典形式的OpenAPI文档"""
        spec = reduce_openapi_spec(yaml_dict)
        try:
            await self._process_spec("temp", "temp.yaml", spec, spec.servers)
        except Exception:
            err = "[OpenAPILoader] 处理OpenAPI文档失败"
            logger.exception(err)
            raise

        return spec


    async def load_one(self, service_id: str, yaml_path: Path, server: str) -> list[NodePool]:
        """加载单个OpenAPI文档，可以直接指定路径"""
        try:
            spec = await self._read_yaml(yaml_path)
        except Exception as e:
            err = f"[OpenAPILoader] 加载OpenAPI文档{yaml_path}失败"
            logger.exception(err)
            raise RuntimeError(err) from e

        yaml_filename = yaml_path.name
        server = spec.servers
        try:
            api_nodes = await self._process_spec(service_id, yaml_filename, spec, server)
        except Exception as e:
            err = f"[OpenAPILoader] 处理OpenAPI文档{yaml_filename}失败"
            logger.exception(err)
            raise RuntimeError(err) from e

        return [
            NodePool(
                _id=node.id,
                name=node.name,
                description=node.description,
                call_id=node.call_id,
                service_id=service_id,
                override_input=node.override_input.model_dump(
                    exclude_none=True,
                    by_alias=True,
                )
                if node.override_input
                else {},
                override_output={},
                known_params=node.known_params,
            )
            for node in api_nodes
        ]


    async def save_one(self, yaml_path: Path, yaml_dict: dict[str, Any]) -> None:
        """保存单个OpenAPI文档"""
        try:
            yaml.add_representer(str, yaml_str_presenter)
            yaml_data = yaml.safe_dump(
                yaml_dict,
                allow_unicode=True,
                sort_keys=False,
            )
            await yaml_path.write_text(yaml_data)
        except Exception as e:
            if await yaml_path.exists():
                await yaml_path.unlink()
            err = f"[OpenAPILoader] 保存OpenAPI文档{yaml_path}失败"
            logger.exception(err)
            raise RuntimeError(err) from e
