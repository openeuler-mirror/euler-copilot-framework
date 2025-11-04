# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""JSON编码器模块"""

import json
from typing import Any
from uuid import UUID


class UUIDEncoder(json.JSONEncoder):
    """支持UUID类型的JSON编码器"""

    def default(self, obj: Any) -> Any:
        """
        重写default方法以支持UUID类型序列化

        :param obj: 待序列化的对象
        :return: 序列化后的对象
        """
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)
