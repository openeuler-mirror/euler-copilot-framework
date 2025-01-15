"""OpenAPI文档相关操作

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from collections.abc import Sequence
from copy import deepcopy
from typing import Any, Optional

from pydantic import BaseModel


class ReducedOpenAPISpec(BaseModel):
    """精简后的OpenAPISpec文档"""

    servers: list[dict]
    id: str
    description: str
    endpoints: list[tuple[str, str, dict]]


def _retrieve_ref(path: str, schema: dict) -> dict:
    """从OpenAPI文档中找到$ref对应的schema"""
    components = path.split("/")
    if components[0] != "#":
        msg = (
            "ref paths are expected to be URI fragments, meaning they should start "
            "with #."
        )
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
                full_ref = _dereference_refs_helper(
                    ref, full_schema, skip_keys, processed_refs,
                )
                processed_refs.remove(v)
                return full_ref
            elif isinstance(v, (list, dict)):
                obj_out[k] = _dereference_refs_helper(
                    v, full_schema, skip_keys, processed_refs,
                )
            else:
                obj_out[k] = v
        return obj_out

    if isinstance(obj, list):
        return [
            _dereference_refs_helper(el, full_schema, skip_keys, processed_refs)
            for el in obj
        ]

    return obj


def _infer_skip_keys(
    obj: Any, full_schema: dict, processed_refs: Optional[set[str]] = None,  # noqa: ANN401
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


def reduce_openapi_spec(spec: dict) -> ReducedOpenAPISpec:
    """解析和处理OpenAPI文档"""
    # 只支持get, post, patch, put, delete API
    endpoints = [
        (f"{operation_name.upper()} {route}", docs.get("description"), docs)
        for route, operation in spec["paths"].items()
        for operation_name, docs in operation.items()
        if operation_name in ["get", "post", "patch", "put", "delete"]
    ]

    # 强制去除ref
    endpoints = [
        (name, description, dereference_refs(docs, full_schema=spec))
        for name, description, docs in endpoints
    ]

    # 只提取关键字段【可修改】
    def reduce_endpoint_docs(docs: dict) -> dict:
        out = {}
        if docs.get("description"):
            out["description"] = docs.get("description")
        if docs.get("parameters"):
            out["parameters"] = [
                parameter
                for parameter in docs.get("parameters", [])
                if parameter.get("required")
            ]
        if "200" in docs["responses"]:
            out["responses"] = docs["responses"]["200"]
        if docs.get("requestBody"):
            out["requestBody"] = docs.get("requestBody")
        return out

    endpoints = [
        (name, description, reduce_endpoint_docs(docs))
        for name, description, docs in endpoints
    ]
    return ReducedOpenAPISpec(
        servers=spec["servers"],
        id=spec["info"]["title"],
        description=spec["info"].get("description", ""),
        endpoints=endpoints,
    )
