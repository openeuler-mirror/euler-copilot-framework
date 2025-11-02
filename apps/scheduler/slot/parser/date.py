# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""日期解析器"""

import io
import logging
import sys
from datetime import datetime
from typing import Any

import pytz

# 临时屏蔽 jionlp 的广告输出
_old_stdout = sys.stdout
sys.stdout = io.StringIO()
try:
    from jionlp import parse_time
finally:
    sys.stdout = _old_stdout

from jsonschema import TypeChecker

from apps.schemas.enum_var import SlotType

logger = logging.getLogger(__name__)


class SlotDateParser:
    """日期解析器"""

    type: SlotType = SlotType.TYPE
    name: str = "date"


    @classmethod
    def convert(cls, data: str, **kwargs) -> tuple[str, str]:  # noqa: ANN003
        """
        将日期字符串转换为日期对象

        返回的格式：(开始时间, 结束时间)
        """
        time_format = kwargs.get("date", "%Y-%m-%d %H:%M:%S")
        result = parse_time(data)
        if "time" in result:
            start_time, end_time = result["time"]
        else:
            logger.error("Date解析失败: %s", data)
            return data, data

        try:
            # 将日期格式化为指定格式
            start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S").astimezone(pytz.timezone("Asia/Shanghai"))
            start_time = start_time.strftime(time_format)

            end_time = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S").astimezone(pytz.timezone("Asia/Shanghai"))
            end_time = end_time.strftime(time_format)
        except Exception:
            logger.exception("[Slot] Date解析失败: %s", data)
            return data, data

        return start_time, end_time


    @classmethod
    def type_validate(cls, _checker: TypeChecker, instance: Any) -> bool:
        """生成对应类型的验证器"""
        if not isinstance(instance, str):
            return False

        try:
            parse_time(instance)
        except Exception:
            logger.exception("[Slot] Date解析失败: %s", instance)
            return False

        return True
