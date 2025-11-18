# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""自动参数填充工具"""

import json
from jsonschema import validate
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Self, ClassVar

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field

from apps.llm.enum import DefaultModelId
from apps.llm.function import FunctionLLM, JsonGenerator
from apps.llm.reasoning import ReasoningLLM
from apps.llm.function import FunctionLLM
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.slot.prompt import SLOT_GEN_PROMPT
from apps.scheduler.call.slot.schema import SlotInput, SlotOutput
from apps.scheduler.slot.slot import Slot as SlotProcessor
from apps.schemas.enum_var import CallOutputType, CallType, LanguageType
from apps.schemas.pool import NodePool
from apps.schemas.scheduler import CallInfo, CallOutputChunk, CallVars
from apps.schemas.config import LLMConfig, FunctionCallConfig
from apps.services.llm import LLMManager

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor


class Slot(CoreCall, input_model=SlotInput, output_model=SlotOutput):
    """参数填充工具"""
    chat_llm_id: str = Field(
        description="对话大模型ID", default=DefaultModelId.DEFAULT_CHAT_MODEL_ID.value)
    func_llm_id: str = Field(description="Function Call大模型ID",
                             default=DefaultModelId.DEFAULT_FUNCTION_CALL_MODEL_ID.value)
    data: dict[str, Any] = Field(description="当前输入", default={})
    current_schema: dict[str, Any] = Field(description="当前Schema", default={})
    summary: str = Field(description="背景信息总结", default="")
    facts: list[str] = Field(description="事实信息", default=[])
    step_num: int = Field(description="历史步骤数", default=1)
    i18n_info: ClassVar[dict[str, dict]] = {
        LanguageType.CHINESE: {
            "name": "参数自动填充",
            "type": CallType.TOOL,
            "description": "根据步骤历史，自动填充参数",
        },
        LanguageType.ENGLISH: {
            "name": "Parameter Auto-Fill",
            "type": CallType.TOOL,
            "description": "Auto-fill parameters based on step history.",
        },
    }

    async def _llm_slot_fill(
        self, remaining_schema: dict[str, Any], language: LanguageType = LanguageType.CHINESE
    ) -> tuple[str, dict[str, Any]]:
        """使用大模型填充参数；若大模型解析度足够，则直接返回结果"""
        env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template = env.from_string(SLOT_GEN_PROMPT[language])

        conversation = [
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": template.render(
                    current_tool={
                        "name": self.name,
                        "description": self.description,
                    },
                    schema=remaining_schema,
                    history_data=self._flow_history,
                    summary=self.summary,
                    question=self._question,
                    facts=self.facts,
                ),
            },
        ]

        # 使用大模型进行尝试
        chat_llm = await LLMManager.get_llm_by_id(self.chat_llm_id)
        chat_llm_config = LLMConfig(
            provider=chat_llm.provider,
            api_key=chat_llm.openai_api_key,
            endpoint=chat_llm.openai_base_url,
            model=chat_llm.model_name,
            max_tokens=chat_llm.max_tokens
        )
        reasoning = ReasoningLLM(llm_config=chat_llm_config)
        answer = ""
        async for chunk in reasoning.call(messages=conversation, streaming=False):
            answer += chunk
        self.tokens.input_tokens += reasoning.input_tokens
        self.tokens.output_tokens += reasoning.output_tokens
        data = None
        try:
            data = json.loads(answer)
            validate(instance=data, schema=remaining_schema)
        except Exception:
            pass
        if data is not None:
            return answer, data
        # 使用JsonGenerator进行解析
        try:
            data = JsonGenerator._parse_result_by_stack(
                answer, remaining_schema)
        except Exception:  # noqa: BLE001
            data = {}
        return answer, data

    async def _function_slot_fill(self, answer: str, remaining_schema: dict[str, Any]) -> dict[str, Any]:
        """使用FunctionCall填充参数"""
        conversation = [
            {"role": "user", "content": self._question},
            {"role": "assistant", "content": answer},
        ]
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
        json_gen = JsonGenerator(
            query=self._question,
            conversation=conversation,
            schema=remaining_schema,
            func_call_llm=func_call_llm
        )
        return await json_gen.generate()

    async def instance(self, executor: "StepExecutor", node: NodePool | None, **kwargs: Any) -> Self:
        """实例化Call类（实例方法版本）"""
        # 重置或初始化实例属性
        self.name = executor.step.step.name
        self.description = executor.step.step.description
        self.facts = executor.background.facts
        self.summary = executor.task.runtime.summary
        self.node = node
        self.func_llm_id = executor.func_call_llm_id
        self.chat_llm_id = executor.chat_llm_id
        # 处理额外关键字参数
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def _init(self, call_vars: CallVars) -> SlotInput:
        """初始化"""
        self._flow_history = []
        self._question = call_vars.question
        for key in call_vars.history_order[:-self.step_num]:
            self._flow_history += [call_vars.history[key]]

        if not self.current_schema:
            return SlotInput(
                remaining_schema={},
            )

        self._processor = SlotProcessor(self.current_schema)
        remaining_schema = self._processor.check_json(self.data)

        return SlotInput(
            remaining_schema=remaining_schema,
        )

    async def _exec(
        self, input_data: dict[str, Any], language: LanguageType = LanguageType.CHINESE
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """执行参数填充"""
        data = SlotInput(**input_data)

        # 使用LLM填充参数
        if not data.remaining_schema:
            yield CallOutputChunk(
                type=CallOutputType.DATA,
                content=SlotOutput(
                    slot_data=input_data,
                    remaining_schema={},
                ).model_dump(by_alias=True, exclude_none=True),
            )
            return
        answer, slot_data = await self._llm_slot_fill(data.remaining_schema, language)

        slot_data = self._processor.convert_json(slot_data)
        remaining_schema = self._processor.check_json(slot_data)
        if remaining_schema:
            slot_data = await self._function_slot_fill(answer, remaining_schema)
            slot_data = self._processor.convert_json(slot_data)
            remaining_schema = self._processor.check_json(slot_data)

        # 再次检查
        remaining_schema = self._processor.check_json(slot_data)
        yield CallOutputChunk(
            type=CallOutputType.DATA,
            content=SlotOutput(
                slot_data=slot_data,
                remaining_schema=remaining_schema,
            ).model_dump(by_alias=True, exclude_none=True),
        )
