# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""提取事实工具"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Self

from pydantic import Field

from apps.llm import json_generator
from apps.models import LanguageType, NodeInfo
from apps.scheduler.call.core import CoreCall
from apps.schemas.enum_var import CallOutputType
from apps.schemas.scheduler import CallInfo, CallOutputChunk, CallVars
from apps.services.user_tag import UserTagManager

from .prompt import DOMAIN_FUNCTION, DOMAIN_PROMPT, FACTS_FUNCTION, FACTS_PROMPT
from .schema import (
    DomainGen,
    FactsGen,
    FactsInput,
    FactsOutput,
)

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor


class FactsCall(CoreCall, input_model=FactsInput, output_model=FactsOutput):
    """提取事实工具"""

    answer: str = Field(description="用户输入")


    @classmethod
    def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
        """返回Call的名称和描述"""
        i18n_info = {
            LanguageType.CHINESE: CallInfo(name="提取事实", description="从对话上下文和文档片段中提取事实。"),
            LanguageType.ENGLISH: CallInfo(
                name="Fact Extraction",
                description="Extract facts from the conversation context and document snippets.",
            ),
        }
        return i18n_info[language]


    @classmethod
    async def instance(cls, executor: "StepExecutor", node: NodeInfo | None, **kwargs: Any) -> Self:
        """初始化工具"""
        obj = cls(
            answer=executor.task.runtime.fullAnswer,
            name=executor.step.step.name,
            description=executor.step.step.description,
            node=node,
            **kwargs,
        )

        await obj._set_input(executor)
        return obj


    async def _init(self, call_vars: CallVars) -> FactsInput:
        """初始化工具"""
        # 组装必要变量
        message = [
            {"role": "user", "content": call_vars.question},
            {"role": "assistant", "content": self.answer},
        ]

        return FactsInput(
            user_id=call_vars.ids.user_id,
            message=message,
        )


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        data = FactsInput(**input_data)

        # 组装conversation消息
        facts_prompt = FACTS_PROMPT[self._sys_vars.language]
        facts_conversation = [
            {"role": "system", "content": "You are a helpful assistant."},
            *data.message,
            {"role": "user", "content": facts_prompt},
        ]

        # 提取事实信息
        facts_result = await json_generator.generate(
            function=FACTS_FUNCTION[self._sys_vars.language],
            conversation=facts_conversation,
            language=self._sys_vars.language,
        )
        facts_obj = FactsGen.model_validate(facts_result)

        # 组装conversation消息
        domain_prompt = DOMAIN_PROMPT[self._sys_vars.language]
        domain_conversation = [
            {"role": "system", "content": "You are a helpful assistant."},
            *data.message,
            {"role": "user", "content": domain_prompt},
        ]

        # 更新用户画像
        domain_result = await json_generator.generate(
            function=DOMAIN_FUNCTION[self._sys_vars.language],
            conversation=domain_conversation,
            language=self._sys_vars.language,
        )
        domain_list = DomainGen.model_validate(domain_result)

        for domain in domain_list.keywords:
            await UserTagManager.update_user_domain_by_user_and_domain_name(data.user_id, domain)

        yield CallOutputChunk(
            type=CallOutputType.DATA,
            content=FactsOutput(
                facts=facts_obj.facts,
                domain=domain_list.keywords,
            ).model_dump(by_alias=True, exclude_none=True),
        )


    async def exec(self, executor: "StepExecutor", input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        async for chunk in self._exec(input_data):
            content = chunk.content
            if not isinstance(content, dict):
                err = "[FactsCall] 工具输出格式错误"
                raise TypeError(err)
            executor.task.runtime.fact = FactsOutput.model_validate(content).facts
            yield chunk
