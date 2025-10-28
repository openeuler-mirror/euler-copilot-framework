# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用于问题推荐的工具"""

import random
import uuid
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Self

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

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

from .prompt import SUGGEST_PROMPT
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
        # 从 ExecutorBackground 中获取历史问题
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
        # 只有当_app_id不为None时才获取Flow信息
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

        # 获取当前用户的画像
        user_domain_info = await UserTagManager.get_user_domain_by_user_and_topk(data.user_id, 5)
        user_domain = [tag.name for tag in user_domain_info]
        # 初始化Prompt
        prompt_tpl = self._env.from_string(SUGGEST_PROMPT[self._sys_vars.language])

        # 如果设置了configs，则按照configs生成问题
        if self.configs:
            async for output_chunk in self._process_configs(
                prompt_tpl,
                user_domain,
            ):
                yield output_chunk
            return

        # 如果_app_id为None，直接生成N个推荐问题
        if self._app_id is None:
            async for output_chunk in self._generate_general_questions(
                prompt_tpl,
                user_domain,
                self.num,
            ):
                yield output_chunk
            return

        # 如果_app_id不为None，获取App中所有Flow并为每个Flow生成问题
        async for output_chunk in self._generate_questions_for_all_flows(
            prompt_tpl,
            user_domain,
        ):
            yield output_chunk

    async def _generate_questions_from_llm(
        self,
        prompt_tpl: Any,
        tool_info: dict[str, Any] | None,
        user_domain: list[str],
        generated_questions: set[str] | None = None,
        target_num: int | None = None,
    ) -> SuggestGenResult:
        """通过LLM生成问题"""
        # 合并历史问题和已生成问题为question_list
        question_list = list(self._history_questions)
        if generated_questions:
            question_list.extend(list(generated_questions))

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
        result = await self._json(
            messages=messages,
            schema=SuggestGenResult.model_json_schema(),
        )
        return SuggestGenResult.model_validate(result)

    async def _generate_general_questions(
        self,
        prompt_tpl: Any,
        user_domain: list[str],
        target_num: int,
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """生成通用问题（无app_id时）"""
        pushed_questions = 0
        attempts = 0

        # 用于跟踪已经生成过的问题，避免重复
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

            # 过滤掉已经生成过的问题
            unique_questions = [
                q for q in questions.predicted_questions
                if q not in generated_questions
            ]

            # 输出生成的问题，直到达到目标数量
            for question in unique_questions:
                if pushed_questions >= target_num:
                    break

                # 将问题添加到已生成集合中
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
        prompt_tpl: Any,
        user_domain: list[str],
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """为App中所有Flow生成问题"""
        for flow_id, flow_info in self._avaliable_flows.items():
            # 为每个Flow生成一个问题
            questions = await self._generate_questions_from_llm(
                prompt_tpl,
                {
                    "name": flow_id,
                    "description": flow_info,
                },
                user_domain,
            )
            # 随机选择一个生成的问题
            question = questions.predicted_questions[random.randint(0, len(questions.predicted_questions) - 1)]  # noqa: S311

            # 判断是否为当前Flow，设置isHighlight
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
        prompt_tpl: Any,
        user_domain: list[str],
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """处理配置中的问题"""
        for config in self.configs:
            # 如果flow_id为None，生成通用问题
            if config.flow_id is None:
                yield CallOutputChunk(
                    type=CallOutputType.DATA,
                    content=SuggestionOutput(
                        question=config.question,
                        flowName=None,
                        flowId=None,
                        flowDescription=None,
                        isHighlight=False,  # 通用问题不设置高亮
                    ).model_dump(by_alias=True, exclude_none=True),
                )
            else:
                # 检查flow_id是否存在于可用Flow中
                if config.flow_id not in self._avaliable_flows:
                    raise CallError(
                        message="配置的Flow ID不存在",
                        data={},
                    )

                # 判断是否为当前Flow，设置isHighlight
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
