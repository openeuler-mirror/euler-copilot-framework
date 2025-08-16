# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""提取事实工具"""

import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Self, ClassVar

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field

from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.facts.prompt import DOMAIN_PROMPT, FACTS_PROMPT
from apps.scheduler.call.facts.schema import (
    DomainGen,
    FactsGen,
    FactsInput,
    FactsOutput,
)
from apps.schemas.enum_var import CallOutputType, CallType, LanguageType
from apps.schemas.pool import NodePool
from apps.schemas.scheduler import CallInfo, CallOutputChunk, CallVars
from apps.services.user_domain import UserDomainManager

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor


class FactsCall(CoreCall, input_model=FactsInput, output_model=FactsOutput):
    """提取事实工具"""
    answer: str = Field(description="用户输入")
    i18n_info: ClassVar[dict[str, dict]] = {
        LanguageType.CHINESE: {
            "name": "提取事实",
            "type": CallType.TOOL,
            "description": "从对话上下文和文档片段中提取事实。",
        },
        LanguageType.ENGLISH: {
            "name": "Fact Extraction",
            "type": CallType.TOOL,
            "description": "Extract facts from the conversation context and document snippets.",
        },
    }

    @classmethod
    async def instance(cls, executor: "StepExecutor", node: NodePool | None, **kwargs: Any) -> Self:
        """初始化工具"""
        obj = cls(
            answer=executor.task.runtime.answer,
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
            user_sub=call_vars.ids.user_sub,
            message=message,
        )


    async def _exec(
        self, input_data: dict[str, Any], language: LanguageType = LanguageType.CHINESE
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        data = FactsInput(**input_data)
        # jinja2 环境
        env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # 提取事实信息
        facts_tpl = env.from_string(FACTS_PROMPT[language])
        facts_prompt = facts_tpl.render(conversation=data.message)
        try:
            facts_obj: FactsGen = await self._json([
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": facts_prompt},
            ], FactsGen) # type: ignore[arg-type]
        except Exception as e:
            # 如果 LLM 返回格式不正确，使用默认空列表
            logging.warning(f"[FactsCall] 事实提取失败，使用默认值: {e}")
            facts_obj = FactsGen(facts=[])

        # 更新用户画像
        domain_tpl = env.from_string(DOMAIN_PROMPT[language])
        domain_prompt = domain_tpl.render(conversation=data.message)
        try:
            domain_list: DomainGen = await self._json([
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": domain_prompt},
            ], DomainGen) # type: ignore[arg-type]
        except Exception as e:
            # 如果 LLM 返回格式不正确，使用默认空列表
            logging.warning(f"[FactsCall] 域名提取失败，使用默认值: {e}")
            domain_list = DomainGen(keywords=[])

        for domain in domain_list.keywords:
            await UserDomainManager.update_user_domain_by_user_sub_and_domain_name(data.user_sub, domain)

        yield CallOutputChunk(
            type=CallOutputType.DATA,
            content=FactsOutput(
                facts=facts_obj.facts,
                domain=domain_list.keywords,
            ).model_dump(by_alias=True, exclude_none=True),
        )


    async def exec(
        self,
        executor: "StepExecutor",
        input_data: dict[str, Any],
        language: LanguageType = LanguageType.CHINESE,
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        async for chunk in self._exec(input_data, language):
            content = chunk.content
            if not isinstance(content, dict):
                err = "[FactsCall] 工具输出格式错误"
                raise TypeError(err)
            executor.task.runtime.facts = FactsOutput.model_validate(content).facts
            yield chunk
