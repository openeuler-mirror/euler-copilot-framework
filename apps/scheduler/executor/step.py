# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""工作流中步骤相关函数"""

import inspect
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from pydantic import ConfigDict

from apps.models import ExecutorHistory, ExecutorStatus, StepStatus
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.empty import Empty
from apps.scheduler.call.facts.facts import FactsCall
from apps.scheduler.call.slot.schema import SlotOutput
from apps.scheduler.call.slot.slot import Slot
from apps.scheduler.call.summary.summary import Summary
from apps.scheduler.pool.pool import pool
from apps.schemas.enum_var import (
    EventType,
    SpecialCallType,
)
from apps.schemas.message import TextAddContent
from apps.schemas.scheduler import CallError, CallOutputChunk, ExecutorBackground
from apps.schemas.task import StepQueueItem
from apps.services.node import NodeManager

from .base import BaseExecutor

logger = logging.getLogger(__name__)


class StepExecutor(BaseExecutor):
    """工作流中步骤相关函数"""

    step: StepQueueItem
    background: ExecutorBackground

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

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

        # 从Pool中获取对应的Call
        call_cls: type[CoreCall] = await pool.get_call(call_id)

        # 检查Call合法性
        if not await StepExecutor.check_cls(call_cls):
            err = f"[FlowExecutor] 工具 {call_id} 不符合Call标准要求"
            raise ValueError(err)

        return call_cls

    async def init(self) -> None:
        """初始化步骤"""
        logger.info("[StepExecutor] 初始化步骤 %s", self.step.step.name)

        if not self.task.state:
            err = "[StepExecutor] 任务状态不存在"
            logger.error(err)
            raise RuntimeError(err)

        # State写入ID和运行状态
        self.task.state.stepId = self.step.step_id
        self.task.state.stepType = self.step.step.type
        self.task.state.stepName = self.step.step.name

        # 获取并验证Call类
        node_id = self.step.step.node
        # 获取node详情并存储
        try:
            self.node = await NodeManager.get_node(node_id)
        except ValueError:
            logger.info("[StepExecutor] 获取Node失败，为内部Node或ID不存在")
            self.node = None

        if self.node:
            call_cls = await StepExecutor.get_call_cls(self.node.callId)
            self._call_id = self.node.callId
        else:
            # 可能是特殊的内置Node
            call_cls = await StepExecutor.get_call_cls(node_id)
            self._call_id = node_id

        # 初始化Call Class，用户参数会覆盖node的参数
        params: dict[str, Any] = (
            self.node.knownParams if self.node and self.node.knownParams else {}
        )
        if self.step.step.params:
            params.update(self.step.step.params)

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
        await self._check_cancelled()

        if not self.task.state:
            err = "[StepExecutor] 任务状态不存在"
            logger.error(err)
            raise RuntimeError(err)

        # 暂存旧数据
        current_step_id = self.task.state.stepId
        current_step_name = self.task.state.stepName

        # 更新State
        self.task.state.stepId = uuid.uuid4()
        self.task.state.stepName = "自动参数填充"
        self.task.state.stepStatus = StepStatus.RUNNING
        self.task.runtime.time = round(datetime.now(UTC).timestamp(), 2)

        # 初始化填参
        slot_obj = await Slot.instance(
            self,
            self.node,
            data=self.obj.input,
            current_schema=self.obj.input_model.model_json_schema(
                override=self.node.overrideInput if self.node and self.node.overrideInput else {},
            ),
        )
        # 推送填参消息
        await self._push_message(EventType.STEP_INPUT.value, slot_obj.input)
        # 运行填参
        iterator = slot_obj.exec(self, slot_obj.input)
        async for chunk in iterator:
            await self._check_cancelled()
            result: SlotOutput = SlotOutput.model_validate(chunk.content)

        # 如果没有填全，则状态设置为待填参
        if result.remaining_schema:
            self.task.state.stepStatus = StepStatus.PARAM
        else:
            self.task.state.stepStatus = StepStatus.SUCCESS
        await self._push_message(EventType.STEP_OUTPUT.value, result.model_dump(by_alias=True, exclude_none=True))

        # 更新输入
        self.obj.input.update(result.slot_data)

        # 恢复State
        self.task.state.stepId = current_step_id
        self.task.state.stepName = current_step_name


    async def _process_chunk(
        self,
        iterator: AsyncGenerator[CallOutputChunk, None],
        *,
        to_user: bool = False,
    ) -> str | dict[str, Any]:
        """处理Chunk"""
        content: str | dict[str, Any] = ""
        chunk_count = 0

        async for chunk in iterator:
            chunk_count += 1
            if chunk_count % 10 == 0:
                await self._check_cancelled()
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
                    await self._push_message(EventType.TEXT_ADD.value, chunk.content)
                    self.task.runtime.fullAnswer += chunk.content
                else:
                    await self._push_message(self.step.step.type, chunk.content)

        return content


    async def run(self) -> None:
        """运行单个步骤"""
        logger.info("[StepExecutor] 运行步骤 %s", self.step.step.name)
        await self._check_cancelled()

        if not self.task.state:
            err = "[StepExecutor] 任务状态不存在"
            logger.error(err)
            raise RuntimeError(err)

        # 进行自动参数填充
        await self._run_slot_filling()

        # 更新状态
        self.task.state.stepStatus = StepStatus.RUNNING
        self.task.runtime.time = round(datetime.now(UTC).timestamp(), 2)
        # 推送输入
        await self._push_message(EventType.STEP_INPUT.value, self.obj.input)
        await self._check_cancelled()

        # 执行步骤
        iterator = self.obj.exec(self, self.obj.input)

        try:
            content = await self._process_chunk(iterator, to_user=self.obj.to_user)
        except Exception as e:
            logger.exception("[StepExecutor] 运行步骤失败，进行异常处理步骤")
            self.task.state.stepStatus = StepStatus.ERROR
            self.task.state.executorStatus = ExecutorStatus.ERROR
            await self._push_message(EventType.STEP_OUTPUT.value, {})
            if isinstance(e, CallError):
                self.task.state.errorMessage = {
                    "err_msg": e.message,
                    "data": e.data,
                }
            else:
                self.task.state.errorMessage = {
                    "data": {},
                }
            return

        # 更新执行状态
        self.task.state.stepStatus = StepStatus.SUCCESS
        self.task.runtime.fullTime = round(datetime.now(UTC).timestamp(), 2) - self.task.runtime.time

        # 更新history
        if isinstance(content, str):
            output_data = TextAddContent(text=content).model_dump(exclude_none=True, by_alias=True)
        else:
            output_data = content

        # 更新context
        history = ExecutorHistory(
            taskId=self.task.metadata.id,
            executorId=self.task.state.executorId,
            executorName=self.task.state.executorName,
            executorStatus=self.task.state.executorStatus,
            stepId=self.step.step_id,
            stepName=self.step.step.name,
            stepType=self.task.state.stepType,
            stepStatus=self.task.state.stepStatus,
            inputData=self.obj.input,
            outputData=output_data,
        )
        self.task.context.append(history)

        # 推送输出
        await self._push_message(EventType.STEP_OUTPUT.value, output_data)
