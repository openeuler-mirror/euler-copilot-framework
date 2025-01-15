"""JSON处理函数

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

import jsonpath


def escape_path(key: str) -> str:
    """对JSON Path进行处理，转译关键字"""
    key = key.replace("~", "~0")
    return key.replace("/", "~1")


def patch_json(operation_list: list[dict[str, Any]]) -> dict[str, Any]:
    """应用JSON Patch，获得JSON数据"""
    json_data = {}

    while operation_list:
        current_operation = operation_list.pop()
        try:
            jsonpath.patch.apply([current_operation], json_data)
        except Exception:
            operation_list.append(current_operation)
            path_list = current_operation["path"].split("/")
            path_list.pop()
            for i in range(1, len(path_list) + 1):
                path = "/".join(path_list[:i])
                try:
                    jsonpath.resolve(path, json_data)
                    continue
                except Exception:
                    new_operation = {"op": "add", "path": path, "value": {}}
                    operation_list.append(new_operation)

    return json_data
