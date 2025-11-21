# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Flow执行Executor"""

import logging
import uuid
from collections import deque
from datetime import UTC, datetime

from pydantic import Field

from apps.models import (
    ExecutorCheckpoint,
    ExecutorStatus,
    LanguageType,
    StepStatus,
    StepType,
)
from apps.schemas.enum_var import EventType, SpecialCallType
from apps.schemas.flow import Flow, Step
from apps.schemas.request_data import RequestDataApp
from apps.schemas.task import StepQueueItem

from .base import BaseExecutor
from .prompt import FLOW_ERROR_PROMPT
from .step import StepExecutor

logger = logging.getLogger(__name__)

FIXED_STEPS_BEFORE_START = [
    {
        LanguageType.CHINESE: Step(
            name="理解上下文",
            description="使用大模型，理解对话上下文",
            node=SpecialCallType.SUMMARY.value,
            type=SpecialCallType.SUMMARY.value,
        ),
        LanguageType.ENGLISH: Step(
            name="Understand context",
            description="Use large model to understand the context of the dialogue",
            node=SpecialCallType.SUMMARY.value,
            type=SpecialCallType.SUMMARY.value,
        ),
    },
]

FIXED_STEPS_AFTER_END = [
    {
        LanguageType.CHINESE: Step(
            name="记忆存储",
            description="理解对话答案，并存储到记忆中",
            node=SpecialCallType.FACTS.value,
            type=SpecialCallType.FACTS.value,
        ),
        LanguageType.ENGLISH: Step(
            name="Memory storage",
            description="Understand the answer of the dialogue and store it in the memory",
            node=SpecialCallType.FACTS.value,
            type=SpecialCallType.FACTS.value,
        ),
    },
]


class FlowExecutor(BaseExecutor):
    """用于执行工作流的Executor"""

    flow: Flow
    flow_id: str = Field(description="Flow ID")
    post_body_app: RequestDataApp = Field(description="请求体中的app信息")


    async def init(self) -> None:
        """初始化FlowExecutor"""
        logger.info("[FlowExecutor] 加载Executor状态")
        await self._load_history()

        if (
            not self.task.state
            or self.task.state.executorStatus == ExecutorStatus.INIT
        ):
            self.task.state = ExecutorCheckpoint(
                taskId=self.task.metadata.id,
                appId=self.post_body_app.app_id,
                executorId=self.flow_id,
                executorName=self.flow.name,
                executorStatus=ExecutorStatus.RUNNING,
                stepStatus=StepStatus.RUNNING,
                stepId=self.flow.basicConfig.startStep,
                stepName=self.flow.steps[self.flow.basicConfig.startStep].name,
                stepType=str(StepType(self.flow.steps[self.flow.basicConfig.startStep].type)),
            )
        self._reached_end: bool = False
        self.step_queue: deque[StepQueueItem] = deque()


    async def _invoke_runner(self) -> None:
        """单一Step执行"""
        step_runner = StepExecutor(
            msg_queue=self.msg_queue,
            task=self.task,
            step=self.current_step,
            background=self.background,
            question=self.question,
            llm=self.llm,
        )

        await step_runner.init()
        await step_runner.run()

        # 更新Task（已存过库）
        self.task = step_runner.task


    async def _step_process(self) -> None:
        """执行当前queue里面的所有步骤（在用户看来是单一Step）"""
        while True:
            try:
                self.current_step = self.step_queue.pop()
            except IndexError:
                break

            await self._invoke_runner()


    async def _find_next_id(self, step_id: uuid.UUID) -> list[uuid.UUID]:
        """查找下一个节点"""
        next_ids = []
        for edge in self.flow.edges:
            if edge.edge_from == step_id:
                next_ids += [edge.edge_to]
        return next_ids


    async def _find_flow_next(self) -> list[StepQueueItem]:
        """在当前步骤执行前，尝试获取下一步"""
        if not self.task.state:
            err = "[FlowExecutor] 任务状态不存在"
            logger.error(err)
            raise RuntimeError(err)

        if self.task.state.stepId == "end" or not self.task.state.stepId:
            return []
        if self.current_step.step.type == SpecialCallType.CHOICE.value:
            branch_id = self.task.context[-1].outputData["branch_id"]
            if branch_id:
                next_steps = await self._find_next_id(str(self.task.state.stepId) + "." + branch_id)
                logger.info("[FlowExecutor] 分支ID：%s", branch_id)
            else:
                logger.warning("[FlowExecutor] 没有找到分支ID，返回空列表")
                return []
        else:
            next_steps = await self._find_next_id(self.task.state.stepId)
        # 如果step没有任何出边，直接跳到end
        if not next_steps:
            return [
                StepQueueItem(
                    step_id=self.flow.basicConfig.endStep,
                    step=self.flow.steps[self.flow.basicConfig.endStep],
                ),
            ]

        logger.info("[FlowExecutor] 下一步：%s", next_steps)
        return [
            StepQueueItem(
                step_id=next_step,
                step=self.flow.steps[next_step],
            )
            for next_step in next_steps
        ]


    async def run(self) -> None:
        """
        运行流，返回各步骤结果，直到无法继续执行

        数据通过向Queue发送消息的方式传输
        """
        logger.info("[FlowExecutor] 运行工作流")
        await self._check_cancelled()

        if not self.task.state:
            err = "[FlowExecutor] 任务状态不存在"
            logger.error(err)
            raise RuntimeError(err)

        first_step = StepQueueItem(
            step_id=self.task.state.stepId,
            step=self.flow.steps[self.task.state.stepId],
        )

        for step in FIXED_STEPS_BEFORE_START:
            self.step_queue.append(
                StepQueueItem(
                    step_id=uuid.uuid4(),
                    step=step.get(self.task.runtime.language, step[LanguageType.CHINESE]),
                    enable_filling=False,
                    to_user=False,
                ),
            )
        await self._step_process()

        self.step_queue.append(first_step)
        self.task.state.executorStatus = ExecutorStatus.RUNNING

        is_error = False
        while not self._reached_end:
            await self._check_cancelled()
            if self.task.state.stepStatus == StepStatus.ERROR:
                logger.warning("[FlowExecutor] Executor出错，执行错误处理步骤")
                self.step_queue.clear()
                self.step_queue.appendleft(
                    StepQueueItem(
                        step_id=uuid.uuid4(),
                        step=Step(
                            name=(
                                "错误处理" if self.task.runtime.language == LanguageType.CHINESE else "Error Handling"
                            ),
                            description=(
                                "错误处理" if self.task.runtime.language == LanguageType.CHINESE else "Error Handling"
                            ),
                            node=SpecialCallType.LLM.value,
                            type=SpecialCallType.LLM.value,
                            params={
                                "user_prompt": FLOW_ERROR_PROMPT[self.task.runtime.language].replace(
                                    "{{ error_info }}",
                                    self.task.state.errorMessage["err_msg"],
                                ),
                            },
                        ),
                        enable_filling=False,
                        to_user=False,
                    ),
                )
                is_error = True
                self._reached_end = True

            await self._step_process()

            next_step = await self._find_flow_next()
            if not next_step:
                self._reached_end = True
            for step in next_step:
                self.step_queue.append(step)

        if is_error:
            self.task.state.executorStatus = ExecutorStatus.ERROR
        else:
            self.task.state.executorStatus = ExecutorStatus.SUCCESS

        for step in FIXED_STEPS_AFTER_END:
            self.step_queue.append(
                StepQueueItem(
                    step_id=uuid.uuid4(),
                    step=step.get(self.task.runtime.language, step[LanguageType.CHINESE]),
                ),
            )
        await self._step_process()

        # FlowStop需要返回总时间，需要倒推最初的开始时间（当前时间减去当前已用总时间）
        self.task.runtime.time = round(datetime.now(UTC).timestamp(), 2) - self.task.runtime.fullTime
        await self._push_message(EventType.EXECUTOR_STOP.value)
