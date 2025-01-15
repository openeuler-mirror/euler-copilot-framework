"""对API返回值进行解析

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
from textwrap import dedent
from typing import Any, Optional

from untruncate_json import untrunc

from apps.constants import MAX_API_RESPONSE_LENGTH
from apps.entities.plugin import CallResult
from apps.scheduler.slot.slot import Slot


class APISanitizer:
    """对API返回值进行处理"""

    @staticmethod
    def parameters_to_spec(raw_schema: list[dict[str, Any]]) -> dict[str, Any]:
        """将OpenAPI中GET接口List形式的请求体Spec转换为JSON Schema

        :param raw_schema: OpenAPI数据
        :return: 转换后的JSON Schema
        """
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

    @staticmethod
    def _process_response_schema(response_data: str, response_schema: dict[str, Any]) -> str:
        """对API返回值进行逐个字段处理

        :param response_data: API返回值原始数据
        :param response_schema: API返回值JSON Schema
        :return: 处理后的API返回值
        """
        # 工具执行报错，此时为错误信息，不予处理
        try:
            response_dict = json.loads(response_data)
        except Exception:
            return response_data

        # openapi里没有HTTP 200对应的Schema，不予处理
        if not response_schema:
            return response_data

        slot = Slot(response_schema)
        return json.dumps(slot.process_json(response_dict), ensure_ascii=False)


    @staticmethod
    def process(
        response_data: Optional[str], url: str, usage: str, response_schema: dict[str, Any],
    ) -> CallResult:
        """对返回值进行整体处理

        :param response_data: API返回值的原始Dict
        :param url: API地址
        :param question: 用户调用API时的输入
        :param usage: API接口的描述信息
        :param response_schema: API返回值的JSON Schema
        :return: 处理后的返回值，打包为{"output": "xxx", "message": "xxx"}形式
        """
        # 如果结果太长，不使用大模型进行总结；否则使用大模型生成自然语言总结
        if response_data is None:
            return CallResult(
                output={},
                output_schema={},
                message=f"调用接口{url}成功，但返回值为空。",
            )

        if len(response_data) > MAX_API_RESPONSE_LENGTH:
            response_data = response_data[:MAX_API_RESPONSE_LENGTH]
            response_data = response_data[:response_data.rfind(",") - 1]
            response_data = untrunc.complete(response_data)

        response_data = APISanitizer._process_response_schema(response_data, response_schema)

        message = dedent(f"""调用API从外部数据源获取了数据。API和数据源的描述为：{usage}""")

        return CallResult(
            output=json.loads(response_data),
            output_schema=response_schema,
            message=message,
        )
