# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from typing import Union, Dict, Any, List
from untruncate_json import untrunc
import json

from apps.llm import get_llm, get_message_model
from apps.scheduler.parse_json import parse_json


class APISanitizer:
    """
    对API返回值进行处理
    """

    def __init__(self):
        raise NotImplementedError("APISanitizer不可被实例化")

    @staticmethod
    def parameters_to_spec(raw_schema: List[Dict[str, Any]]):
        """
        将OpenAPI中GET接口List形式的请求体Spec转换为JSON Schema
        :param raw_schema: OpenAPI数据
        :return: 转换后的JSON Schema
        """

        schema = {
            "type": "object",
            "required": [],
            "properties": {}
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
    def _process_response_schema(response_data: str, response_schema: Dict[str, Any]) -> str:
        """
        对API返回值进行逐个字段处理
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

        return json.dumps(parse_json(response_dict, response_schema), ensure_ascii=False)


    @staticmethod
    def process_response_data(response_data: Union[str, None], url: str, question: str, usage: str, response_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        对返回值进行整体处理
        :param response_data: API返回值的原始Dict
        :param url: API地址
        :param question: 用户调用API时的输入
        :param usage: API接口的描述信息
        :param response_schema: API返回值的JSON Schema
        :return: 处理后的返回值，打包为{"output": "xxx", "message": "xxx"}形式
        """

        # 如果结果太长，不使用大模型进行总结；否则使用大模型生成自然语言总结
        if response_data is None:
            return {
                "output": "",
                "message": f"调用接口{url}成功，但返回值为空。"
            }

        if len(response_data) > 4096:
            response_data = response_data[:4096]
            response_data = response_data[:response_data.rfind(",") - 1]
            response_data = untrunc.complete(response_data)

        response_data = APISanitizer._process_response_schema(response_data, response_schema)

        llm = get_llm()
        msg_cls = get_message_model(llm)
        messages = [
            msg_cls(role="system",
                    content="你是一个智能助手，能根据用户提供的指令、工具描述信息与工具输出信息，生成自然语言总结信息。要求尽可能详细，不要漏掉关键信息。"),
            msg_cls(role="user", content=f"""## 用户指令
        {question}

        ## 工具用途
        {usage}

        ## 工具输出Schema
        {response_schema}

        ## 工具输出
        {response_data}""")
        ]
        result_summary = llm.invoke(messages, timeout=30)

        return {
            "output": response_data,
            "message": result_summary.content
        }
