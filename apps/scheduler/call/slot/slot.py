"""参数填充工具"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Self

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field

from apps.entities.enum_var import CallOutputType
from apps.entities.pool import NodePool
from apps.entities.scheduler import CallInfo, CallOutputChunk, CallVars
from apps.llm.patterns.json_gen import Json
from apps.llm.reasoning import ReasoningLLM
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.slot.schema import SLOT_GEN_PROMPT, SlotInput, SlotOutput
from apps.scheduler.slot.slot import Slot as SlotProcessor

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor


class Slot(CoreCall, input_model=SlotInput, output_model=SlotOutput):
    """参数填充工具"""

    data: dict[str, Any] = Field(description="当前输入", default={})
    current_schema: dict[str, Any] = Field(description="当前Schema", default={})
    summary: str = Field(description="背景信息总结", default="")
    facts: list[str] = Field(description="事实信息", default=[])
    step_num: int = Field(description="历史步骤数", default=1)


    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(name="参数自动填充", description="根据步骤历史，自动填充参数")


    async def _llm_slot_fill(self, remaining_schema: dict[str, Any]) -> dict[str, Any]:
        """使用LLM填充参数"""
        env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template = env.from_string(SLOT_GEN_PROMPT)

        conversation = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": template.render(
                current_tool={
                    "name": self.name,
                    "description": self.description,
                },
                schema=remaining_schema,
                history_data=self._flow_history,
                summary=self.summary,
                question=self._question,
                facts=self.facts,
            )},
        ]

        # 使用大模型进行尝试
        reasoning = ReasoningLLM()
        answer = ""
        async for chunk in reasoning.call(messages=conversation, streaming=False):
            answer += chunk
        self.tokens.input_tokens += reasoning.input_tokens
        self.tokens.output_tokens += reasoning.output_tokens

        conversation = [
            {"role": "user", "content": f"""
                    用户问题：{self._question}

                    参考数据：
                    {answer}
                """,
            },
        ]
        return await Json().generate(
            conversation=conversation,
            spec=remaining_schema,
        )

    @classmethod
    async def instance(cls, executor: "StepExecutor", node: NodePool | None, **kwargs: Any) -> Self:
        """实例化Call类"""
        obj = cls(
            name=executor.step.step.name,
            description=executor.step.step.description,
            facts=executor.background.facts,
            summary=executor.task.runtime.summary,
            node=node,
            **kwargs,
        )
        await obj._set_input(executor)
        return obj


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


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
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
        slot_data = await self._llm_slot_fill(data.remaining_schema)
        slot_data = self._processor.convert_json(slot_data)

        # 再次检查
        remaining_schema = self._processor.check_json(slot_data)
        yield CallOutputChunk(
            type=CallOutputType.DATA,
            content=SlotOutput(
                slot_data=slot_data,
                remaining_schema=remaining_schema,
            ).model_dump(by_alias=True, exclude_none=True),
        )
