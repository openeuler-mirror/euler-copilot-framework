# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP基类"""

import logging

from apps.models import LanguageType
from apps.schemas.task import TaskData

_logger = logging.getLogger(__name__)


class MCPBase:
    """MCP基类"""

    _user_id: str
    task: TaskData
    _language: LanguageType

    def __init__(self, task: TaskData) -> None:
        """初始化MCP基类"""
        self._user_id = task.metadata.userId
        self.task = task
        self._language = task.runtime.language
