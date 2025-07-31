# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Flow执行Executor"""

import logging
import uuid
from collections import deque
from datetime import UTC, datetime

from pydantic import Field

from apps.scheduler.call.llm.prompt import LLM_ERROR_PROMPT
from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.executor.step import StepExecutor
from apps.schemas.enum_var import EventType, SpecialCallType, FlowStatus, StepStatus
from apps.schemas.flow import Flow, Step
from apps.schemas.request_data import RequestDataApp
from apps.schemas.task import ExecutorState, StepQueueItem
from apps.services.task import TaskManager

logger = logging.getLogger(__name__)
# 开始前的固定步骤
FIXED_STEPS_BEFORE_START = [
    Step(
        name="理解上下文",
        description="使用大模型，理解对话上下文",
        node=SpecialCallType.SUMMARY.value,
        type=SpecialCallType.SUMMARY.value,
    ),
]
# 结束后的固定步骤
FIXED_STEPS_AFTER_END = [
    Step(
        name="记忆存储",
        description="理解对话答案，并存储到记忆中",
        node=SpecialCallType.FACTS.value,
        type=SpecialCallType.FACTS.value,
    ),
]


# 单个流的执行工具
class FlowExecutor(BaseExecutor):
    """用于执行工作流的Executor"""

    flow: Flow
    flow_id: str = Field(description="Flow ID")
    question: str = Field(description="用户输入")
    post_body_app: RequestDataApp = Field(description="请求体中的app信息")
    current_step: StepQueueItem | None = Field(
        description="当前执行的步骤",
        default=None
    )

    async def load_state(self) -> None:
        """从数据库中加载FlowExecutor的状态"""
        logger.info("[FlowExecutor] 加载Executor状态")
        # 尝试恢复State
        if self.task.state:
            self.task.context = await TaskManager.get_context_by_task_id(self.task.id)
        else:
            # 创建ExecutorState
            self.task.state = ExecutorState(
                flow_id=str(self.flow_id),
                flow_name=self.flow.name,
                flow_status=FlowStatus.RUNNING,
                description=str(self.flow.description),
                step_status=StepStatus.RUNNING,
                app_id=str(self.post_body_app.app_id),
                step_id="start",
                step_name="开始",
            )
        self.validate_flow_state(self.task)
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

    async def _find_next_id(self, step_id: str) -> list[str]:
        """查找下一个节点"""
        next_ids = []
        for edge in self.flow.edges:
            if edge.edge_from == step_id:
                next_ids += [edge.edge_to]
        return next_ids

    async def _find_flow_next(self) -> list[StepQueueItem]:
        """在当前步骤执行前，尝试获取下一步"""
        # 如果当前步骤为结束，则直接返回
        if self.task.state.step_id == "end" or not self.task.state.step_id:  # type: ignore[arg-type]
            return []
        if self.current_step.step.type == SpecialCallType.CHOICE.value:
            # 如果是choice节点，获取分支ID
            branch_id = self.task.context[-1].output_data["branch_id"]
            if branch_id:
                next_steps = await self._find_next_id(self.task.state.step_id + "." + branch_id)
                logger.info("[FlowExecutor] 分支ID：%s", branch_id)
            else:
                logger.warning("[FlowExecutor] 没有找到分支ID，返回空列表")
                return []
        else:
            next_steps = await self._find_next_id(self.task.state.step_id)  # type: ignore[arg-type]
        # 如果step没有任何出边，直接跳到end
        if not next_steps:
            return [
                StepQueueItem(
                    step_id="end",
                    step=self.flow.steps["end"],
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
        # 推送Flow开始消息
        await self.push_message(EventType.FLOW_START.value)

        # 获取首个步骤
        first_step = StepQueueItem(
            step_id=self.task.state.step_id,  # type: ignore[arg-type]
            step=self.flow.steps[self.task.state.step_id],  # type: ignore[arg-type]
        )

        # 头插开始前的系统步骤，并执行
        for step in FIXED_STEPS_BEFORE_START:
            self.step_queue.append(StepQueueItem(
                step_id=str(uuid.uuid4()),
                step=step,
                enable_filling=False,
                to_user=False,
            ))
        await self._step_process()

        # 插入首个步骤
        self.step_queue.append(first_step)
        self.task.state.flow_status = FlowStatus.RUNNING  # type: ignore[arg-type]
        # 运行Flow（未达终点）
        is_error = False
        while not self._reached_end:
            # 如果当前步骤出错，执行错误处理步骤
            if self.task.state.step_status == StepStatus.ERROR:  # type: ignore[arg-type]
                logger.warning("[FlowExecutor] Executor出错，执行错误处理步骤")
                self.step_queue.clear()
                self.step_queue.appendleft(StepQueueItem(
                    step_id=str(uuid.uuid4()),
                    step=Step(
                        name="错误处理",
                        description="错误处理",
                        node=SpecialCallType.LLM.value,
                        type=SpecialCallType.LLM.value,
                        params={
                            "user_prompt": LLM_ERROR_PROMPT.replace(
                                "{{ error_info }}",
                                self.task.state.error_info["err_msg"],  # type: ignore[arg-type]
                            ),
                        },
                    ),
                    enable_filling=False,
                    to_user=False,
                ))
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
            self.task.state.flow_status = FlowStatus.ERROR  # type: ignore[arg-type]
        else:
            self.task.state.flow_status = FlowStatus.SUCCESS  # type: ignore[arg-type]

        # 尾插运行结束后的系统步骤
        for step in FIXED_STEPS_AFTER_END:
            self.step_queue.append(StepQueueItem(
                step_id=str(uuid.uuid4()),
                step=step,
            ))
        await self._step_process()

        # FlowStop需要返回总时间，需要倒推最初的开始时间（当前时间减去当前已用总时间）
        self.task.tokens.time = round(datetime.now(UTC).timestamp(), 2) - self.task.tokens.full_time
        # 推送Flow停止消息
        if is_error:
            await self.push_message(EventType.FLOW_FAILED.value)
        else:
            await self.push_message(EventType.FLOW_SUCCESS.value)
