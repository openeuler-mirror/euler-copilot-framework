"""固定值设置器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

from apps.entities.enum_var import SlotType
from apps.scheduler.slot.parser.core import SlotParser


class SlotConstParser(SlotParser):
    """给字段设置固定值"""

    type: SlotType = SlotType.KEYWORD
    name: str = "const"

    @classmethod
    def convert(cls, data: Any, **kwargs) -> Any:  # noqa: ANN003, ANN401
        """生成keyword的验证器

        如果没有对应逻辑则不实现
        """
        raise NotImplementedError

