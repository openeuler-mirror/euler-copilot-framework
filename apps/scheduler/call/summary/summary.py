# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""总结上下文工具"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Self, ClassVar

from pydantic import Field

from apps.llm.patterns.executor import ExecutorSummary
from apps.scheduler.call.core import CoreCall, DataBase
from apps.scheduler.call.summary.schema import SummaryOutput
from apps.schemas.enum_var import CallOutputType, LanguageType
from apps.schemas.pool import NodePool
from apps.schemas.scheduler import (
    CallInfo,
    CallOutputChunk,
    CallVars,
    ExecutorBackground,
)

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor



class Summary(CoreCall, input_model=DataBase, output_model=SummaryOutput):
    """总结工具"""

    context: ExecutorBackground = Field(description="对话上下文")

    i18n_info: ClassVar[dict[str, dict]] = {
        LanguageType.CHINESE: {
            "name": "理解上下文",
            "description": "使用大模型，理解对话上下文",
        },
        LanguageType.ENGLISH: {
            "name": "Context Understanding",
            "description": "Use the foundation model to understand the conversation context",
        },
    }

    @classmethod
    async def instance(cls, executor: "StepExecutor", node: NodePool | None, **kwargs: Any) -> Self:
        """实例化工具"""
        obj = cls(
            context=executor.background,
            name=executor.step.step.name,
            description=executor.step.step.description,
            node=node,
            **kwargs,
        )
        await obj._set_input(executor)
        return obj


    async def _init(self, call_vars: CallVars) -> DataBase:
        """初始化工具，返回输入"""
        return DataBase()

    async def _exec(
        self, _input_data: dict[str, Any], language: LanguageType = LanguageType.CHINESE
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        summary_obj = ExecutorSummary()
        summary = await summary_obj.generate(background=self.context, language=language)
        self.tokens.input_tokens += summary_obj.input_tokens
        self.tokens.output_tokens += summary_obj.output_tokens

        yield CallOutputChunk(type=CallOutputType.TEXT, content=summary)

    async def exec(
        self,
        executor: "StepExecutor",
        input_data: dict[str, Any],
        language: LanguageType = LanguageType.CHINESE,
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        async for chunk in self._exec(input_data, language):
            content = chunk.content
            if not isinstance(content, str):
                err = "[SummaryCall] 工具输出格式错误"
                raise TypeError(err)
            executor.task.runtime.summary = content
            yield chunk
