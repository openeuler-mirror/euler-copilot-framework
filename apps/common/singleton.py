"""给类开启全局单例模式

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from multiprocessing import Lock
from typing import Any, ClassVar


class Singleton(type):
    """用于实现全局单例的MetaClass"""

    _instances: ClassVar[dict[type, Any]] = {}
    _lock = Lock()

    def __call__(cls, *args, **kwargs):  # noqa: ANN002, ANN003, ANN204
        """实现单例模式"""
        if cls not in cls._instances:
            with cls._lock:
                cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
