# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP基类"""

import json
import logging
from typing import Any

from anyio import Path
from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.common.config import config
from apps.models import LanguageType
from apps.schemas.task import TaskData

_logger = logging.getLogger(__name__)
_env = SandboxedEnvironment(
    loader=BaseLoader,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def tojson_filter(value: dict[str, Any]) -> str:
    """将字典转换为紧凑JSON字符串"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


_env.filters["tojson"] = tojson_filter


class MCPBase:
    """MCP基类"""

    _user_id: str
    _language: LanguageType
    _goal: str

    def __init__(self, task: TaskData) -> None:
        """初始化MCP基类"""
        self._user_id = task.metadata.userId
        self._goal = task.runtime.userInput
        self._language = task.runtime.language

    async def _load_prompt(self, prompt_id: str) -> str:
        """
        从Markdown文件加载提示词

        :param prompt_id: 提示词ID,例如 "risk_evaluate" 等
        :return: 提示词内容
        """
        filename = f"{prompt_id}.{self._language.value}.md"
        prompt_file = Path(config.deploy.data_dir) / "prompts" / "system" / "mcp" / filename
        return await prompt_file.read_text(encoding="utf-8")
