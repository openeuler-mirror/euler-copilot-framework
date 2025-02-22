"""OpenAPI文档相关操作

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

from collections.abc import Sequence
from copy import deepcopy
from typing import Any, Optional

from pydantic import BaseModel, Field


class ReducedOpenAPIEndpoint(BaseModel):
    """精简后的OpenAPI文档中的单个API"""

    id: Optional[str] = Field(default=None, description="API的Operation ID")
    uri: str = Field(..., description="API的URI")
    method: str = Field(..., description="API的请求方法")
    name: str = Field(..., description="API的自定义名称")
    description: str = Field(..., description="API的描述信息")
    spec: dict = Field(..., description="API的JSON Schema")


class ReducedOpenAPISpec(BaseModel):
    """精简后的OpenAPISpec文档"""

    id: str
    description: str
    endpoints: list[ReducedOpenAPIEndpoint]


def _retrieve_ref(path: str, schema: dict) -> dict:
    """从OpenAPI文档中找到$ref对应的schema"""
    components = path.split("/")
    if components[0] != "#":
        msg = "ref paths are expected to be URI fragments, meaning they should start with #."
        raise ValueError(msg)
    out = schema
    for component in components[1:]:
        if component in out:
            out = out[component]
        elif component.isdigit() and int(component) in out:
            out = out[int(component)]
        else:
            msg = f"Reference '{path}' not found."
            raise KeyError(msg)
    return deepcopy(out)


def _dereference_refs_helper(
    obj: Any,  # noqa: ANN401
    full_schema: dict[str, Any],
    skip_keys: Sequence[str],
    processed_refs: Optional[set[str]] = None,
) -> Any:  # noqa: ANN401
    """递归地将OpenAPI中的$ref替换为实际的schema"""
    if processed_refs is None:
        processed_refs = set()

    if isinstance(obj, dict):
        obj_out = {}
        for k, v in obj.items():
            if k in skip_keys:
                obj_out[k] = v
            elif k == "$ref":
                if v in processed_refs:
                    continue
                processed_refs.add(v)
                ref = _retrieve_ref(v, full_schema)
                full_ref = _dereference_refs_helper(ref, full_schema, skip_keys, processed_refs)
                processed_refs.remove(v)
                return full_ref
            elif isinstance(v, (list, dict)):
                obj_out[k] = _dereference_refs_helper(v, full_schema, skip_keys, processed_refs)
            else:
                obj_out[k] = v
        return obj_out

    if isinstance(obj, list):
        return [_dereference_refs_helper(el, full_schema, skip_keys, processed_refs) for el in obj]

    return obj


def _infer_skip_keys(
    obj: Any,
    full_schema: dict,
    processed_refs: Optional[set[str]] = None,
) -> list[str]:
    """推断需要跳过的OpenAPI文档中的键"""
    if processed_refs is None:
        processed_refs = set()

    keys = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "$ref":
                if v in processed_refs:
                    continue
                processed_refs.add(v)
                ref = _retrieve_ref(v, full_schema)
                keys.append(v.split("/")[1])
                keys += _infer_skip_keys(ref, full_schema, processed_refs)
            elif isinstance(v, (list, dict)):
                keys += _infer_skip_keys(v, full_schema, processed_refs)
    elif isinstance(obj, list):
        for el in obj:
            keys += _infer_skip_keys(el, full_schema, processed_refs)
    return keys


def dereference_refs(
    schema_obj: dict,
    *,
    full_schema: Optional[dict] = None,
) -> dict:
    """将OpenAPI中的$ref替换为实际的schema"""
    full_schema = full_schema or schema_obj
    skip_keys = _infer_skip_keys(schema_obj, full_schema)
    return _dereference_refs_helper(schema_obj, full_schema, skip_keys)


def reduce_endpoint_docs(docs: dict) -> dict:
    """精简API文档"""
    out = {}
    if docs.get("description"):
        out["description"] = docs.get("description")
    if docs.get("parameters"):
        out["parameters"] = [parameter for parameter in docs.get("parameters", []) if parameter.get("required")]
    if "200" in docs["responses"]:
        out["responses"] = docs["responses"]["200"]
    if docs.get("requestBody"):
        out["requestBody"] = docs.get("requestBody")
    return out


def reduce_openapi_spec(spec: dict) -> ReducedOpenAPISpec:
    """解析和处理OpenAPI文档"""
    # 只支持get, post, patch, put, delete API；强制去除ref；提取关键字段
    endpoints = []
    for route, operation in spec["paths"].items():
        for operation_name, docs in operation.items():
            if operation_name in ["get", "post", "patch", "put", "delete"] and (
                not hasattr(docs, "deprecated") or not docs.deprecated
            ):
                name = docs.get("summary")
                description = docs.get("description")
                missing_fields = []
                if not name:
                    missing_fields.append("summary")
                if not description:
                    missing_fields.append("description")
                if missing_fields:
                    msg = f'Endpoint error at "{operation_name.upper()} {route}": missing {", ".join(missing_fields)}.'
                    raise ValueError(msg)
                endpoint = ReducedOpenAPIEndpoint(
                    id=docs.get("operationId", None),
                    uri=route,
                    method=operation_name,
                    name=name,
                    description=description,
                    spec=reduce_endpoint_docs(dereference_refs(docs, full_schema=spec)),
                )
                endpoints.append(endpoint)

    return ReducedOpenAPISpec(
        id=spec["info"]["title"],
        description=spec["info"].get("description", ""),
        endpoints=endpoints,
    )
