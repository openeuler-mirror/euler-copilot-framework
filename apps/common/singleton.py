# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from threading import Lock


class Singleton(type):
    """
    用于实现全局单例的Class
    """

    _instances = {}
    _lock: Lock = Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
