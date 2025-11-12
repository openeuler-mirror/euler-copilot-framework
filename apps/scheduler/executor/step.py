# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""工作流中步骤相关函数"""

import inspect
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
import json
import jsonschema
from pydantic import ConfigDict, Field

from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.empty import Empty
from apps.scheduler.call.facts.facts import FactsCall
from apps.scheduler.call.reply.direct_reply import DirectReply
from apps.scheduler.call.slot.schema import SlotOutput
from apps.scheduler.call.slot.slot import Slot
from apps.scheduler.call.summary.summary import Summary
from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.executor.step_config import should_use_direct_conversation_format
from apps.scheduler.pool.pool import Pool
from apps.scheduler.variable.integration import VariableIntegration
from apps.schemas.enum_var import (
    EventType,
    SpecialCallType,
    StepStatus
)
from apps.schemas.message import TextAddContent
from apps.schemas.scheduler import CallError, CallOutputChunk
from apps.schemas.task import FlowStepHistory, StepQueueItem
from apps.services.node import NodeManager
from apps.llm.enum import DefaultModelId
logger = logging.getLogger(__name__)


class StepExecutor(BaseExecutor):
    """工作流中步骤相关函数"""

    step: StepQueueItem

    chat_llm_id: str = Field(description="对话使用的大模型ID",
                             default=DefaultModelId.DEFAULT_CHAT_MODEL_ID.value)
    enable_thinking: bool = Field(description="是否启用思维链", default=False)
    func_call_llm_id: str = Field(
        description="Function Call使用的大模型ID",
        default=DefaultModelId.DEFAULT_FUNCTION_CALL_MODEL_ID.value,
    )
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    def __init__(self, **kwargs: Any) -> None:
        """初始化"""
        super().__init__(**kwargs)
        self.validate_flow_state(self.task)

    @staticmethod
    async def check_cls(call_cls: Any) -> bool:
        """检查Call是否符合标准要求"""
        flag = True
        if not hasattr(call_cls, "_init") or not callable(call_cls._init):  # noqa: SLF001
            flag = False
        if not hasattr(call_cls, "_exec") or not inspect.isasyncgenfunction(call_cls._exec):  # noqa: SLF001
            flag = False
        if not hasattr(call_cls, "info") or not callable(call_cls.info):
            flag = False
        return flag

    @staticmethod
    async def get_call_cls(call_id: str) -> type[CoreCall]:
        """获取并验证Call类"""
        # 特判，用于处理隐藏节点
        if call_id == SpecialCallType.EMPTY.value:
            return Empty
        if call_id == SpecialCallType.SUMMARY.value:
            return Summary
        if call_id == SpecialCallType.FACTS.value:
            return FactsCall
        if call_id == SpecialCallType.SLOT.value:
            return Slot
        if call_id == SpecialCallType.DIRECT_REPLY.value:
            return DirectReply
        if call_id == SpecialCallType.START.value:
            return Empty  # start节点使用Empty类
        if call_id == SpecialCallType.END.value:
            return Empty  # end节点使用Empty类

        # 从Pool中获取对应的Call
        call_cls: type[CoreCall] = await Pool().get_call(call_id)

        # 检查Call合法性
        if not await StepExecutor.check_cls(call_cls):
            err = f"[FlowExecutor] 工具 {call_id} 不符合Call标准要求"
            raise ValueError(err)

        return call_cls

    async def init(self) -> None:
        """初始化步骤"""
        logger.info("[StepExecutor] 初始化步骤 %s", self.step.step.name)

        # State写入ID和运行状态
        self.task.state.step_id = self.step.step_id  # type: ignore[arg-type]
        # type: ignore[arg-type]
        self.task.state.step_name = self.step.step.name

        # 获取并验证Call类
        node_id = self.step.step.node
        # 获取node详情并存储
        try:
            self.node = await NodeManager.get_node(node_id)
        except ValueError:
            logger.info("[StepExecutor] 获取Node失败，为内部Node或ID不存在")
            self.node = None

        if self.node:
            call_cls = await StepExecutor.get_call_cls(self.node.call_id)
            self._call_id = self.node.call_id
        else:
            # 可能是特殊的内置Node
            call_cls = await StepExecutor.get_call_cls(node_id)
            self._call_id = node_id

        # 初始化Call Class，用户参数会覆盖node的参数
        params: dict[str, Any] = (
            self.node.known_params if self.node and self.node.known_params else {}
        )
        if self.step.step.params:
            input_params = self.step.step.params.get("input_parameters", {})
            if isinstance(input_params, dict):
                params.update(input_params)

        # 对于LLM调用，注入enable_thinking参数
        if self._call_id == SpecialCallType.LLM.value:
            params["llm_id"] = self.chat_llm_id
            params['enable_thinking'] = self.background.enable_thinking

        try:
            self.obj = await call_cls.instance(self, self.node, **params)
        except Exception:
            logger.exception("[StepExecutor] 初始化Call失败")
            raise

    async def _run_slot_filling(self) -> None:
        """运行自动参数填充；相当于特殊Step，但是不存库"""
        # 判断是否需要进行自动参数填充
        if not self.obj.enable_filling:
            return

        # 暂存旧数据
        current_step_id = self.task.state.step_id  # type: ignore[arg-type]
        current_step_name = self.task.state.step_name  # type: ignore[arg-type]

        # 更新State
        self.task.state.step_id = str(uuid.uuid4())  # type: ignore[arg-type]
        self.task.state.step_name = "自动参数填充"  # type: ignore[arg-type]
        # type: ignore[arg-type]
        self.task.state.step_status = StepStatus.RUNNING
        self.task.tokens.time = round(datetime.now(UTC).timestamp(), 2)

        # 初始化填参
        slot_obj = Slot()
        await slot_obj.instance(
            self,
            self.node,
            data=self.obj.input,
            current_schema=self.obj.input_model.model_json_schema(
                override=self.node.override_input if self.node and self.node.override_input else {},
            ),
        )
        # 推送填参消息
        await self.push_message(EventType.STEP_INPUT.value, slot_obj.input)
        # 运行填参
        iterator = slot_obj.exec(self, slot_obj.input)
        async for chunk in iterator:
            result: SlotOutput = SlotOutput.model_validate(chunk.content)
        self.task.tokens.input_tokens += slot_obj.tokens.input_tokens
        self.task.tokens.output_tokens += slot_obj.tokens.output_tokens

        # 如果没有填全，则状态设置为待填参
        if result.remaining_schema:
            # type: ignore[arg-type]
            self.task.state.step_status = StepStatus.PARAM
        else:
            # type: ignore[arg-type]
            self.task.state.step_status = StepStatus.SUCCESS
        await self.push_message(EventType.STEP_OUTPUT.value, result.model_dump(by_alias=True, exclude_none=True))

        # 更新输入
        self.obj.input.update(result.slot_data)

        # 恢复State
        self.task.state.step_id = current_step_id  # type: ignore[arg-type]
        self.task.state.step_name = current_step_name  # type: ignore[arg-type]
        self.task.tokens.input_tokens += self.obj.tokens.input_tokens
        self.task.tokens.output_tokens += self.obj.tokens.output_tokens

    async def _process_chunk(
        self,
        iterator: AsyncGenerator[CallOutputChunk, None],
        *,
        to_user: bool = False,
    ) -> str | dict[str, Any]:
        """处理Chunk"""
        content: str | dict[str, Any] = ""

        async for chunk in iterator:
            logging.error(f"StepExecutor接收到chunk: {chunk}")
            if not isinstance(chunk, CallOutputChunk):
                err = "[StepExecutor] 返回结果类型错误"
                logger.error(err)
                raise TypeError(err)
            if isinstance(chunk.content, str):
                if not isinstance(content, str):
                    content = ""
                content += chunk.content
            else:
                if not isinstance(content, dict):
                    content = {}
                content = chunk.content
            if to_user:
                if isinstance(chunk.content, str):
                    await self.push_message(EventType.TEXT_ADD.value, chunk.content)
                    self.task.runtime.answer += chunk.content
                else:
                    # 🔑 修复：非字符串内容应该通过step.output事件发送，而不是使用step.type
                    await self.push_message(EventType.STEP_OUTPUT.value, chunk.content)

        return content

    async def _save_output_parameters_to_variables(self, output_data: str | dict[str, Any]) -> None:
        """保存输出参数到变量池，并进行类型验证"""
        output_data_schema = self.obj.output_model.model_json_schema()
        try:
            jsonschema.validate(instance=output_data,
                                schema=output_data_schema)
        except Exception as e:
            logger.error(
                f"[StepExecutor] 输出数据不符合output_data_schema: {e}")
            # type: ignore[assignment]
            self.task.state.step_status = StepStatus.ERROR
            raise ValueError(
                f"输出数据不符合output_data_schema: {e}") from e

        var_prefix = f"{self.step.step_id}"
        if not isinstance(output_data_schema, dict):
            await VariableIntegration.save_conversation_variable(
                var_name=f"{var_prefix}",
                value=output_data,
                description=f"步骤 {self.step.step_id} 的完整输出",
                user_sub=self.task.ids.user_sub,
                # type: ignore[arg-type]
                conversation_id=self.task.ids.conversation_id
            )
        else:
            if "properties" in output_data_schema:
                output_data_schema: dict = output_data_schema["properties"]
            else:
                raise ValueError(
                    f"[StepExecutor] 步骤 {self.step.step_id} 的 output_data_schema 格式错误，缺少 items 字段")
            for param_name, param_config in output_data_schema.items():
                param_value = None
                if param_name in output_data:
                    param_value = output_data[param_name]
                if param_value is not None:
                    await VariableIntegration.save_conversation_variable(
                        var_name=f"{var_prefix}.{param_name}",
                        value=param_value,
                        description=param_config.get(
                            "description", f"步骤 {self.step.step_id} 的输出参数 {param_name}"),
                        user_sub=self.task.ids.user_sub,
                        # type: ignore[arg-type]
                        conversation_id=self.task.ids.conversation_id
                    )

    async def run(self) -> None:
        """运行单个步骤"""
        self.validate_flow_state(self.task)

        # 进行自动参数填充
        await self._run_slot_filling()

        # 更新状态
        # type: ignore[arg-type]
        self.task.state.step_status = StepStatus.RUNNING
        self.task.tokens.time = round(datetime.now(UTC).timestamp(), 2)
        # 推送输入
        await self.push_message(EventType.STEP_INPUT.value, self.obj.input)

        # 执行步骤
        iterator = self.obj.exec(self, self.obj.input,
                                 language=self.task.language)

        try:
            content = await self._process_chunk(iterator, to_user=self.obj.to_user)
        except Exception as e:
            logger.exception("[StepExecutor] 运行步骤失败，进行异常处理步骤")
            # type: ignore[arg-type]
            self.task.state.step_status = StepStatus.ERROR

            # 构建错误输出数据
            if isinstance(e, CallError):
                error_output = {
                    "error": e.message,
                    "message": e.message,
                    "data": e.data,
                }
                self.task.state.error_info = {  # type: ignore[arg-type]
                    "err_msg": e.message,
                    "data": e.data,
                }
            else:
                error_output = {
                    "error": str(e),
                    "message": str(e),
                    "data": {},
                }
                self.task.state.error_info = {  # type: ignore[arg-type]
                    "err_msg": str(e),
                    "data": {},
                }

            # 发送包含错误信息的输出
            await self.push_message(EventType.STEP_OUTPUT.value, error_output)
            return

        # 更新执行状态
        # type: ignore[arg-type]
        self.task.state.step_status = StepStatus.SUCCESS
        self.task.tokens.input_tokens += self.obj.tokens.input_tokens
        self.task.tokens.output_tokens += self.obj.tokens.output_tokens
        self.task.tokens.full_time += round(datetime.now(
            UTC).timestamp(), 2) - self.task.tokens.time

        # 更新history
        if isinstance(content, str):
            # 处理空字符串的情况，避免TextAddContent验证失败
            if not content:
                content = " "  # 使用一个空格作为占位符
            output_data = TextAddContent(text=content).model_dump(
                exclude_none=True, by_alias=True)
        else:
            output_data = content

        # 保存output_parameters到变量池
        await self._save_output_parameters_to_variables(output_data)

        # 更新context
        history = FlowStepHistory(
            task_id=self.task.id,
            flow_id=self.task.state.flow_id,  # type: ignore[arg-type]
            flow_name=self.task.state.flow_name,  # type: ignore[arg-type]
            flow_status=self.task.state.flow_status,  # type: ignore[arg-type]
            step_id=self.step.step_id,
            step_name=self.step.step.name,
            step_description=self.step.step.description,
            step_status=self.task.state.step_status,  # type: ignore[arg-type]
            input_data=self.obj.input,
            output_data=output_data,
        )
        self.task.context.append(history)

        try:
            await self.push_message(EventType.STEP_OUTPUT.value, output_data)
        except Exception as e:
            logger.error(
                f"[StepExecutor] {self.step.step.name} - push_message调用失败: {e}")
            raise
