# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用于问题推荐的工具"""

import random
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Self, ClassVar

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from apps.common.security import Security
from apps.llm.function import FunctionLLM
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.suggest.prompt import SUGGEST_PROMPT
from apps.scheduler.call.suggest.schema import (
    SingleFlowSuggestionConfig,
    SuggestGenResult,
    SuggestionInput,
    SuggestionOutput,
)
from apps.schemas.config import FunctionCallConfig
from apps.schemas.enum_var import CallOutputType, CallType, LanguageType
from apps.schemas.pool import NodePool
from apps.schemas.record import RecordContent
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)
from apps.services.record import RecordManager
from apps.services.user_domain import UserDomainManager
from apps.services.llm import LLMManager
if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor


class Suggestion(CoreCall, input_model=SuggestionInput, output_model=SuggestionOutput):
    """问题推荐"""
    llm_id: str | None = Field(
        default=None, description="用于问题推荐的LLM ID，若不填则使用应用默认的LLM")
    to_user: bool = Field(default=True, description="是否将推荐的问题推送给用户")

    configs: list[SingleFlowSuggestionConfig] = Field(
        description="问题推荐配置", default=[])
    num: int = Field(default=3, ge=1, le=6,
                     description="推荐问题的总数量（必须大于等于configs中涉及的Flow的数量）")

    context: SkipJsonSchema[list[dict[str, str]]] = Field(
        description="Executor的上下文", exclude=True)
    conversation_id: SkipJsonSchema[str] = Field(
        description="对话ID", exclude=True)

    i18n_info: ClassVar[dict[str, dict]] = {
        LanguageType.CHINESE: {
            "name": "问题推荐",
            "type": CallType.DEFAULT,
            "description": "在答案下方显示推荐的下一个问题",
        },
        LanguageType.ENGLISH: {
            "name": "Question Suggestion",
            "type": CallType.DEFAULT,
            "description": "Display the suggested next question under the answer",
        },
    }

    @classmethod
    async def instance(cls, executor: "StepExecutor", node: NodePool | None, **kwargs: Any) -> Self:
        """初始化"""
        context = [
            {
                "role": "user",
                "content": executor.task.runtime.question,
            },
            {
                "role": "assistant",
                "content": executor.task.runtime.answer,
            },
        ]
        obj = cls(
            llm_id=executor.func_call_llm_id,
            name=executor.step.step.name,
            description=executor.step.step.description,
            node=node,
            context=context,
            conversation_id=executor.task.ids.conversation_id,
            **kwargs,
        )
        await obj._set_input(executor)
        return obj

    async def _init(self, call_vars: CallVars) -> SuggestionInput:
        """初始化"""
        from apps.services.appcenter import AppCenterManager
        self._history_questions = await self._get_history_questions(
            call_vars.ids.user_sub,
            self.conversation_id,
        )
        self._app_id = call_vars.ids.app_id
        self._flow_id = call_vars.ids.flow_id
        app_metadata = await AppCenterManager.fetch_app_data_by_id(self._app_id)
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        self._avaliable_flows = {}
        for flow in app_metadata.flows:
            self._avaliable_flows[flow.id] = {
                "name": flow.name,
                "description": flow.description,
            }

        return SuggestionInput(
            question=call_vars.question,
            user_sub=call_vars.ids.user_sub,
            history_questions=self._history_questions,
        )

    async def _get_history_questions(self, user_sub: str, conversation_id: str) -> list[str]:
        """获取当前对话的历史问题"""
        records = await RecordManager.query_record_by_conversation_id(
            user_sub,
            conversation_id,
            15,
        )

        history_questions = []
        for record in records:
            record_data = RecordContent.model_validate_json(
                Security.decrypt(record.content, record.key))
            history_questions.append(record_data.question)
        return history_questions

    async def get_func_llm_id(self) -> FunctionLLM:
        """获取用于函数调用的LLM ID"""
        func_call_llm = await LLMManager.get_llm_by_id(self.func_llm_id)
        func_call_llm_config = FunctionCallConfig(
            provider=func_call_llm.provider,
            endpoint=func_call_llm.openai_base_url,
            api_key=func_call_llm.openai_api_key,
            model=func_call_llm.model_name,
            max_tokens=func_call_llm.max_tokens,
            temperature=0.7,
        )
        func_call_llm = FunctionLLM(func_call_llm_config)
        return func_call_llm

    async def _exec(
        self, input_data: dict[str, Any], language: LanguageType = LanguageType.CHINESE
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """运行问题推荐"""
        data = SuggestionInput(**input_data)

        # 配置不正确
        if self.num < len(self.configs):
            raise CallError(
                message="推荐问题的数量必须大于等于配置的数量",
                data={},
            )

        # 获取当前用户的画像
        user_domain = await UserDomainManager.get_user_domain_by_user_sub_and_topk(data.user_sub, 5)
        # 已推送问题数量
        pushed_questions = 0
        # 初始化Prompt
        prompt_tpl = self._env.from_string(SUGGEST_PROMPT[language])
        func_llm = await self.get_func_llm_id()
        # 先处理configs
        for config in self.configs:
            if config.flow_id not in self._avaliable_flows:
                raise CallError(
                    message="配置的Flow ID不存在",
                    data={},
                )

            if config.question:
                question = config.question
            else:
                prompt = prompt_tpl.render(
                    conversation=self.context,
                    history=self._history_questions,
                    tool={
                        "name": config.flow_id,
                        "description": self._avaliable_flows[config.flow_id],
                    },
                    preference=user_domain,
                )
                result = await func_llm.call(
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": prompt},
                    ],
                    schema=SuggestGenResult.model_json_schema(),
                )
                questions = SuggestGenResult.model_validate(result)
                question = questions.predicted_questions[random.randint(0, len(questions.predicted_questions) - 1)]  # noqa: S311

            yield CallOutputChunk(
                type=CallOutputType.DATA,
                content=SuggestionOutput(
                    question=question,
                    flowName=self._avaliable_flows[config.flow_id]["name"],
                    flowId=config.flow_id,
                    flowDescription=self._avaliable_flows[config.flow_id]["description"],
                ).model_dump(by_alias=True, exclude_none=True),
            )
            pushed_questions += 1

        while pushed_questions < self.num:
            prompt = prompt_tpl.render(
                conversation=self.context,
                history=self._history_questions,
                tool={
                    "name": self._flow_id,
                    "description": self._avaliable_flows[self._flow_id],
                },
                preference=user_domain,
            )
            result = await func_llm.call(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                schema=SuggestGenResult.model_json_schema(),
            )
            questions = SuggestGenResult.model_validate(result)
            question = questions.predicted_questions[random.randint(0, len(questions.predicted_questions) - 1)]  # noqa: S311

            # 只会关联当前flow
            for question in questions.predicted_questions:
                if pushed_questions >= self.num:
                    break

                yield CallOutputChunk(
                    type=CallOutputType.DATA,
                    content=SuggestionOutput(
                        question=question,
                        flowName=self._avaliable_flows[self._flow_id]["name"],
                        flowId=self._flow_id,
                        flowDescription=self._avaliable_flows[self._flow_id]["description"],
                    ).model_dump(by_alias=True, exclude_none=True),
                )
                pushed_questions += 1
