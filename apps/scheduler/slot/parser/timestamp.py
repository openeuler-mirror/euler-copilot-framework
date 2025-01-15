"""时间戳解析器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from datetime import datetime
from typing import Any, Union

import pytz
from jsonschema import TypeChecker

from apps.constants import LOGGER
from apps.entities.enum import SlotType
from apps.scheduler.slot.parser.core import SlotParser


class SlotTimestampParser(SlotParser):
    """时间戳解析器"""

    type: SlotType = SlotType.TYPE
    name: str = "timestamp"

    @classmethod
    def convert(cls, data: Union[str, int], **_kwargs) -> str:  # noqa: ANN003
        """将日期字符串转换为日期对象"""
        try:
            timestamp_int = int(data)
            return datetime.fromtimestamp(timestamp_int, tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            LOGGER.error(f"Timestamp解析失败: {data}; 错误: {e!s}")
            return str(data)


    @classmethod
    def type_validate(cls, _checker: TypeChecker, instance: Any) -> bool:  # noqa: ANN401
        """生成type的验证器

        若没有对应的处理逻辑则返回True
        """
        # 检查是否为string、int或者float类型
        if not isinstance(instance, (str, int, float)):
            return False

        # 检查是否为时间戳
        try:
            timestamp_int = int(instance)
            datetime.fromtimestamp(timestamp_int, tz=pytz.timezone("Asia/Shanghai"))
        except Exception:
            return False

        return True

