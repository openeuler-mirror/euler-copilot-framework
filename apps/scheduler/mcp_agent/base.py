# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP基类"""

import logging
from typing import Any

from apps.llm import JsonGenerator, LLMConfig
from apps.models import LanguageType
from apps.schemas.task import TaskData

_logger = logging.getLogger(__name__)


class MCPBase:
    """MCP基类"""

    _user_sub: str
    _llm: LLMConfig
    _goal: str
    _language: LanguageType

    def __init__(self, task: TaskData, llm: LLMConfig) -> None:
        """初始化MCP基类"""
        self._user_sub = task.metadata.userSub
        self._llm = llm
        self._goal = task.runtime.userInput
        self._language = task.runtime.language

    async def get_reasoning_result(self, prompt: str) -> str:
        """获取推理结果"""
        # 调用推理大模型
        message = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Please provide a JSON response based on the above information and schema."},
        ]
        result = ""
        async for chunk in self._llm.reasoning.call(
            message,
            streaming=False,
        ):
            result += chunk.content or ""

        return result

    async def get_json_result(self, result: str, function: dict[str, Any]) -> dict[str, Any]:
        """解析推理结果；function使用OpenAI标准Function格式"""
        json_generator = JsonGenerator(
            self._llm,
            "Please provide a JSON response based on the above information and schema.\n\n",
            [
                {"role": "user", "content": result},
            ],
            function,
        )
        return await json_generator.generate()
