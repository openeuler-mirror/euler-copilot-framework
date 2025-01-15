"""Gitee ID 白名单 Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import os
from pathlib import Path
from typing import ClassVar

from apps.common.config import config
from apps.common.singleton import Singleton
from apps.constants import LOGGER


class GiteeIDManager(metaclass=Singleton):
    """Gitee ID 白名单 Manager"""

    whitelist: ClassVar[list[str]] = []

    def __init__(self) -> None:
        """读取白名单文件"""
        config_path = os.getenv("CONFIG")
        if not config_path:
            err = "CONFIG is not set."
            raise ValueError(err)

        if not config["GITEE_WHITELIST"]:
            LOGGER.warning("未设置GITEE白名单路径，不做处理。")
            return

        path = Path(config_path, config["GITEE_WHITELIST"])
        with open(path, encoding="utf-8") as f:
            for line in f:
                line_strip = line.strip()
                if not line_strip or line_strip.startswith("#"):
                    continue
                GiteeIDManager.whitelist.append(line_strip)

    @staticmethod
    def check_user_exist_or_not(gitee_id: str) -> bool:
        """检查用户是否在白名单中

        :param gitee_id: Gitee ID
        :return: 是否在白名单中
        """
        return gitee_id in GiteeIDManager.whitelist
