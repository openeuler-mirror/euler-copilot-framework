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
# 开始前的固定步骤
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
# 结束后的固定步骤
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


# 单个流的执行工具
class FlowExecutor(BaseExecutor):
    """用于执行工作流的Executor"""

    flow: Flow
    flow_id: str = Field(description="Flow ID")
    post_body_app: RequestDataApp = Field(description="请求体中的app信息")


    async def init(self) -> None:
        """初始化FlowExecutor"""
        logger.info("[FlowExecutor] 加载Executor状态")
        await self._load_history()

        # 尝试恢复State
        if (
            not self.task.state
            or self.task.state.executorStatus == ExecutorStatus.INIT
        ):
            # 创建ExecutorState
            self.task.state = ExecutorCheckpoint(
                taskId=self.task.metadata.id,
                appId=self.post_body_app.app_id,
                executorId=self.flow_id,
                executorName=self.flow.name,
                executorStatus=ExecutorStatus.RUNNING,
                stepStatus=StepStatus.RUNNING,
                stepId=self.flow.basicConfig.startStep,
                stepName=self.flow.steps[self.flow.basicConfig.startStep].name,
                # 先转换为StepType，再转换为str，确定Flow的类型在其中
                stepType=str(StepType(self.flow.steps[self.flow.basicConfig.startStep].type)),
            )
        # 是否到达Flow结束终点（变量）
        self._reached_end: bool = False
        self.step_queue: deque[StepQueueItem] = deque()


    async def _invoke_runner(self) -> None:
        """单一Step执行"""
        # 创建步骤Runner
        step_runner = StepExecutor(
            msg_queue=self.msg_queue,
            task=self.task,
            step=self.current_step,
            background=self.background,
            question=self.question,
            llm=self.llm,
        )

        # 初始化步骤
        await step_runner.init()
        # 运行Step
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

            # 执行Step
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

        # 如果当前步骤为结束，则直接返回
        if self.task.state.stepId == "end" or not self.task.state.stepId:
            return []
        if self.current_step.step.type == SpecialCallType.CHOICE.value:
            # 如果是choice节点，获取分支ID
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

        if not self.task.state:
            err = "[FlowExecutor] 任务状态不存在"
            logger.error(err)
            raise RuntimeError(err)

        # 获取首个步骤
        first_step = StepQueueItem(
            step_id=self.task.state.stepId,
            step=self.flow.steps[self.task.state.stepId],
        )

        # 头插开始前的系统步骤，并执行
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

        # 插入首个步骤
        self.step_queue.append(first_step)
        self.task.state.executorStatus = ExecutorStatus.RUNNING

        # 运行Flow（未达终点）
        is_error = False
        while not self._reached_end:
            # 如果当前步骤出错，执行错误处理步骤
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
                # 错误处理后结束
                self._reached_end = True

            # 执行步骤
            await self._step_process()

            # 查找下一个节点
            next_step = await self._find_flow_next()
            if not next_step:
                # 没有下一个节点，结束
                self._reached_end = True
            for step in next_step:
                self.step_queue.append(step)

        # 更新Task状态
        if is_error:
            self.task.state.executorStatus = ExecutorStatus.ERROR
        else:
            self.task.state.executorStatus = ExecutorStatus.SUCCESS

        # 尾插运行结束后的系统步骤
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
        # 推送Flow停止消息
        await self._push_message(EventType.EXECUTOR_STOP.value)
