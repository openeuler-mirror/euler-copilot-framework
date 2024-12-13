# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from datetime import datetime
import pytz
from typing import Any, Dict, Union


def parse_json(json_value: Any, spec_data: Dict[str, Any]):
    """
    使用递归的方式对JSON返回值进行处理
    :param json_value: 返回值中的字段
    :param spec_data: 返回值字段对应的JSON Schema
    :return: 处理后的这部分返回值字段
    """

    if "allOf" in spec_data:
        processed_dict = {}
        for item in spec_data["allOf"]:
            processed_dict.update(parse_json(json_value, item))
        return processed_dict

    if "type" in spec_data:
        if spec_data["type"] == "timestamp" and (isinstance(json_value, str) or isinstance(json_value, int)):
            processed_timestamp =  _process_timestamp(json_value)
            return processed_timestamp
        if spec_data["type"] == "array" and isinstance(json_value, list):
            processed_list = []
            for item in json_value:
                processed_list.append(parse_json(item, spec_data["items"]))
            return processed_list
        if spec_data["type"] == "object" and isinstance(json_value, dict):
            processed_dict = {}
            for key, val in json_value.items():
                if key not in spec_data["properties"]:
                    processed_dict[key] = val
                    continue
                processed_dict[key] = parse_json(val, spec_data["properties"][key])
            return processed_dict

        return json_value


def _process_timestamp(timestamp_str: Union[str, int]) -> str:
    """
    将type为timestamp的字段转换为大模型可读的日期表示
    :param timestamp_str: 时间戳
    :return: 转换后的北京时间
    """
    try:
        timestamp_int = int(timestamp_str)
    except Exception:
        return timestamp_str

    time = datetime.fromtimestamp(timestamp_int, tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    return time
