# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP基类"""

import json
import logging
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.models import LanguageType
from apps.scheduler.mcp.prompt import MEMORY_TEMPLATE
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

    @staticmethod
    async def assemble_memory(task: TaskData) -> list[dict[str, str]]:
        """组装记忆"""
        history = []
        template = MEMORY_TEMPLATE[task.runtime.language]

        for index, item in enumerate(task.context, start=1):
            # 用户消息：步骤描述和工具调用
            step_goal = item.extraData["step_goal"]
            user_content = _env.from_string(template).render(
                msg_type="user",
                step_index=index,
                step_goal=step_goal,
                step_name=item.stepName,
                input_data=item.inputData,
            )
            history.append({
                "role": "user",
                "content": user_content,
            })

            # 助手消息：步骤执行结果
            assistant_content = _env.from_string(template).render(
                msg_type="assistant",
                step_index=index,
                step_status=item.stepStatus.value,
                output_data=item.outputData,
            )
            history.append({
                "role": "assistant",
                "content": assistant_content,
            })
        return history
