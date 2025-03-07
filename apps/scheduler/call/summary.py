"""总结上下文工具

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from apps.entities.scheduler import CallVars, ExecutorBackground
from apps.llm.patterns.executor import ExecutorSummary
from apps.scheduler.call.core import CoreCall


class SummaryOutput(BaseModel):
    """总结工具的输出"""

    summary: str = Field(description="对问答上下文的总结内容")


class Summary(CoreCall, ret_type=SummaryOutput):
    """总结工具"""

    name: ClassVar[str] = "理解上下文"
    description: ClassVar[str] = "使用大模型，理解对话上下文"


    async def init(self, syscall_vars: CallVars, **kwargs: Any) -> dict[str, Any]:
        """初始化工具"""
        self._context: ExecutorBackground = kwargs["context"]
        self._task_id: str = syscall_vars.task_id
        if not self._context or not isinstance(self._context, list):
            err = "context参数必须是一个列表"
            raise ValueError(err)

        return {
            "task_id": self._task_id,
        }


    async def exec(self) -> dict[str, Any]:
        """执行工具"""
        summary = await ExecutorSummary().generate(self._task_id, background=self._context)
        return SummaryOutput(summary=summary).model_dump(by_alias=True, exclude_none=True)
