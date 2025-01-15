"""日期解析器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from datetime import datetime
from typing import Any

import pytz
from jionlp import parse_time
from jsonschema import TypeChecker

from apps.constants import LOGGER
from apps.entities.enum import SlotType
from apps.scheduler.slot.parser.core import SlotParser


class SlotDateParser(SlotParser):
    """日期解析器"""

    type: SlotType = SlotType.TYPE
    name: str = "date"


    @classmethod
    def convert(cls, data: str, **kwargs) -> tuple[str, str]:  # noqa: ANN003
        """将日期字符串转换为日期对象

        返回的格式：(开始时间, 结束时间)
        """
        time_format = kwargs.get("date", "%Y-%m-%d %H:%M:%S")
        result = parse_time(data)
        if "time" in result:
            start_time, end_time = result["time"]
        else:
            LOGGER.error(f"Date解析失败: {data}")
            return data, data

        try:
            # 将日期格式化为指定格式
            start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S").astimezone(pytz.timezone("Asia/Shanghai"))
            start_time = start_time.strftime(time_format)

            end_time = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S").astimezone(pytz.timezone("Asia/Shanghai"))
            end_time = end_time.strftime(time_format)
        except Exception as e:
            LOGGER.error(f"Date解析失败: {data}; 错误: {e!s}")
            return data, data

        return start_time, end_time


    @classmethod
    def type_validate(cls, _checker: TypeChecker, instance: Any) -> bool:  # noqa: ANN401
        """生成对应类型的验证器"""
        if not isinstance(instance, str):
            return False

        try:
            parse_time(instance)
        except Exception:
            return False

        return True
