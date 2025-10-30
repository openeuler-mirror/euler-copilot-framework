# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用于问题推荐的工具"""

import random
import uuid
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Self

from jinja2 import BaseLoader, Template
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from apps.llm import json_generator
from apps.models import LanguageType, NodeInfo
from apps.scheduler.call.core import CoreCall
from apps.schemas.enum_var import CallOutputType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)
from apps.services.user_tag import UserTagManager

from .prompt import SUGGEST_FUNCTION, SUGGEST_PROMPT
from .schema import (
    SingleFlowSuggestionConfig,
    SuggestGenResult,
    SuggestionInput,
    SuggestionOutput,
)

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor


class Suggestion(CoreCall, input_model=SuggestionInput, output_model=SuggestionOutput):
    """问题推荐"""

    to_user: bool = Field(default=True, description="是否将推荐的问题推送给用户")

    configs: list[SingleFlowSuggestionConfig] = Field(description="问题推荐配置", default=[])
    num: int = Field(default=3, ge=1, le=6, description="推荐问题的总数量（当appId为None时使用）")

    conversation_id: SkipJsonSchema[uuid.UUID | None] = Field(description="对话ID", exclude=True)


    @classmethod
    def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
        """返回Call的名称和描述"""
        i18n_info = {
            LanguageType.CHINESE: CallInfo(name="问题推荐", description="在答案下方显示推荐的下一个问题"),
            LanguageType.ENGLISH: CallInfo(
                name="Question Suggestion",
                description="Display the suggested next question under the answer",
            ),
        }
        return i18n_info[language]


    @classmethod
    async def instance(cls, executor: "StepExecutor", node: NodeInfo | None, **kwargs: Any) -> Self:
        """初始化"""
        obj = cls(
            name=executor.step.step.name,
            description=executor.step.step.description,
            node=node,
            conversation_id=executor.task.metadata.conversationId,
            **kwargs,
        )
        await obj._set_input(executor)
        return obj


    async def _init(self, call_vars: CallVars) -> SuggestionInput:
        """初始化"""
        self._history_questions = call_vars.background.history_questions
        self._app_id = call_vars.ids.app_id
        self._flow_id = call_vars.ids.executor_id
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        self._avaliable_flows = {}
        from apps.services.flow import FlowManager  # noqa: PLC0415

        if self._app_id is not None:
            flows = await FlowManager.get_flows_by_app_id(self._app_id)
            for flow in flows:
                self._avaliable_flows[flow.id] = {
                    "name": flow.name,
                    "description": flow.description,
                }

        return SuggestionInput(
            question=call_vars.question,
            user_id=call_vars.ids.user_id,
            history_questions=self._history_questions,
        )

    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """运行问题推荐"""
        data = SuggestionInput(**input_data)

        user_domain_info = await UserTagManager.get_user_domain_by_user_and_topk(data.user_id, 5)
        user_domain = [tag.name for tag in user_domain_info]
        prompt_tpl = self._env.from_string(SUGGEST_PROMPT[self._sys_vars.language])

        if self.configs:
            async for output_chunk in self._process_configs():
                yield output_chunk
            return

        if self._app_id is None:
            async for output_chunk in self._generate_general_questions(
                prompt_tpl,
                user_domain,
                self.num,
            ):
                yield output_chunk
            return

        async for output_chunk in self._generate_questions_for_all_flows(
            prompt_tpl,
            user_domain,
        ):
            yield output_chunk

    async def _generate_questions_from_llm(
        self,
        prompt_tpl: Template,
        tool_info: dict[str, Any] | None,
        user_domain: list[str],
        generated_questions: set[str] | None = None,
        target_num: int | None = None,
    ) -> SuggestGenResult:
        """通过LLM生成问题"""
        prompt = prompt_tpl.render(
            history=self._history_questions,
            generated=list(generated_questions) if generated_questions else None,
            tool=tool_info,
            preference=user_domain,
            target_num=target_num,
        )
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            *self._sys_vars.background.conversation,
            {"role": "user", "content": prompt},
        ]
        result = await json_generator.generate(
            function=SUGGEST_FUNCTION[self._sys_vars.language],
            conversation=messages,
            language=self._sys_vars.language,
        )
        return SuggestGenResult.model_validate(result)

    async def _generate_general_questions(
        self,
        prompt_tpl: Template,
        user_domain: list[str],
        target_num: int,
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """生成通用问题（无app_id时）"""
        pushed_questions = 0
        attempts = 0
        generated_questions = set()

        while pushed_questions < target_num and attempts < self.num:
            attempts += 1
            questions = await self._generate_questions_from_llm(
                prompt_tpl,
                None,
                user_domain,
                generated_questions,
                target_num,
            )

            unique_questions = [
                q for q in questions.predicted_questions
                if q not in generated_questions
            ]

            for question in unique_questions:
                if pushed_questions >= target_num:
                    break

                generated_questions.add(question)

                yield CallOutputChunk(
                    type=CallOutputType.DATA,
                    content=SuggestionOutput(
                        question=question,
                        flowName=None,
                        flowId=None,
                        flowDescription=None,
                    ).model_dump(by_alias=True, exclude_none=True),
                )
                pushed_questions += 1

    async def _generate_questions_for_all_flows(
        self,
        prompt_tpl: Template,
        user_domain: list[str],
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """为App中所有Flow生成问题"""
        for flow_id, flow_info in self._avaliable_flows.items():
            questions = await self._generate_questions_from_llm(
                prompt_tpl,
                {
                    "name": flow_id,
                    "description": flow_info,
                },
                user_domain,
            )
            question = questions.predicted_questions[random.randint(0, len(questions.predicted_questions) - 1)]  # noqa: S311
            is_highlight = (flow_id == self._flow_id)

            yield CallOutputChunk(
                type=CallOutputType.DATA,
                content=SuggestionOutput(
                    question=question,
                    flowName=flow_info["name"],
                    flowId=flow_id,
                    flowDescription=flow_info["description"],
                    isHighlight=is_highlight,
                ).model_dump(by_alias=True, exclude_none=True),
            )

    async def _process_configs(
        self,
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """处理配置中的问题"""
        for config in self.configs:
            if config.flow_id is None:
                yield CallOutputChunk(
                    type=CallOutputType.DATA,
                    content=SuggestionOutput(
                        question=config.question,
                        flowName=None,
                        flowId=None,
                        flowDescription=None,
                        isHighlight=False,
                    ).model_dump(by_alias=True, exclude_none=True),
                )
            else:
                if config.flow_id not in self._avaliable_flows:
                    raise CallError(
                        message="配置的Flow ID不存在",
                        data={},
                    )

                is_highlight = (config.flow_id == self._flow_id)

                yield CallOutputChunk(
                    type=CallOutputType.DATA,
                    content=SuggestionOutput(
                        question=config.question,
                        flowName=self._avaliable_flows[config.flow_id]["name"],
                        flowId=config.flow_id,
                        flowDescription=self._avaliable_flows[config.flow_id]["description"],
                        isHighlight=is_highlight,
                    ).model_dump(by_alias=True, exclude_none=True),
                )
