"""Flow执行Executor

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import asyncio
import inspect
import logging
from typing import Any, Optional

import ray
from pydantic import BaseModel, ConfigDict, Field
from ray import actor

from apps.entities.enum_var import StepStatus
from apps.entities.flow import Flow, FlowError, Step
from apps.entities.request_data import RequestDataApp
from apps.entities.scheduler import CallVars, ExecutorBackground
from apps.entities.task import ExecutorState, TaskBlock
from apps.llm.patterns.executor import ExecutorSummary
from apps.manager.node import NodeManager
from apps.manager.task import TaskManager
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.empty import Empty
from apps.scheduler.call.llm import LLM
from apps.scheduler.executor.message import (
    push_flow_start,
    push_flow_stop,
    push_step_input,
    push_step_output,
    push_text_output,
)
from apps.scheduler.slot.slot import Slot

logger = logging.getLogger("ray")


# 单个流的执行工具
class Executor(BaseModel):
    """用于执行工作流的Executor"""

    flow_id: str = Field(description="Flow ID")
    flow: Flow = Field(description="工作流数据")
    task: TaskBlock = Field(description="任务信息")
    question: str = Field(description="用户输入")
    queue: actor.ActorHandle = Field(description="消息队列")
    post_body_app: RequestDataApp = Field(description="请求体中的app信息")
    executor_background: ExecutorBackground = Field(description="Executor的背景信息")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )
    """Pydantic配置"""


    async def load_state(self) -> None:
        """从数据库中加载FlowExecutor的状态"""
        logger.info("[FlowExecutor] 加载Executor状态")
        # 尝试恢复State
        if self.task.flow_state:
            self.flow_state = self.task.flow_state
            self.task.flow_context = await TaskManager.get_flow_history_by_task_id(self.task.record.task_id)
        else:
            # 创建ExecutorState
            self.flow_state = ExecutorState(
                flow_id=str(self.flow_id),
                description=str(self.flow.description),
                status=StepStatus.RUNNING,
                app_id=str(self.post_body_app.app_id),
                step_id="start",
                step_name="开始",
                ai_summary="",
                filled_data=self.post_body_app.params,
            )
        # 是否结束运行
        self._can_continue = True
        # 向用户输出的内容
        self._final_answer = ""


    async def _check_cls(self, call_cls: Any) -> bool:
        """检查Call是否符合标准要求"""
        flag = True
        if not hasattr(call_cls, "name") or not isinstance(call_cls.name, str):
            flag = False
        if not hasattr(call_cls, "description") or not isinstance(call_cls.description, str):
            flag = False
        if not hasattr(call_cls, "exec") or not asyncio.iscoroutinefunction(call_cls.exec):
            flag = False
        if not hasattr(call_cls, "stream") or not inspect.isasyncgenfunction(call_cls.stream):
            flag = False
        return flag


    # TODO: 默认错误处理步骤
    async def _run_error(self, step: FlowError) -> dict[str, Any]:
        """运行错误处理步骤"""
        return {}


    async def _get_call_cls(self, node_id: str) -> type[CoreCall]:
        """获取并验证Call类"""
        # 检查flow_state是否为空
        if not self.flow_state:
            err = "[FlowExecutor] flow_state为空"
            raise ValueError(err)

        # 特判
        if node_id == "Empty":
            return Empty

        # 获取对应Node的call_id
        call_id = await NodeManager.get_node_call_id(node_id)
        # 从Pool中获取对应的Call
        pool = ray.get_actor("pool")
        call_cls: type[CoreCall] = await pool.get_call.remote(call_id)

        # 检查Call合法性
        if not await self._check_cls(call_cls):
            err = f"[FlowExecutor] 工具 {node_id} 不符合Call标准要求"
            raise ValueError(err)

        return call_cls


    async def _process_slots(self, call_obj: Any) -> tuple[bool, Optional[dict[str, Any]]]:
        """处理slot参数"""
        if not (hasattr(call_obj, "slot_schema") and call_obj.slot_schema):
            return True, None

        slot_processor = Slot(call_obj.slot_schema)
        remaining_schema, slot_data = await slot_processor.process(
            self.flow_state.filled_data,
            self.post_body_app.params,
            {
                "task_id": self.task.record.task_id,
                "question": self.question,
                "thought": self.flow_state.ai_summary,
                "previous_output": await self._get_last_output(self.task),
            },
        )

        # 保存Schema至State
        self.flow_state.remaining_schema = remaining_schema
        self.flow_state.filled_data.update(slot_data)

        # 如果还有未填充的部分，则返回False
        if remaining_schema:
            self._can_continue = False
            self.flow_state.status = StepStatus.RUNNING
            # 推送空输入输出
            self.task = await push_step_input(self.task, self.queue, self.flow_state, {})
            self.flow_state.status = StepStatus.PARAM
            self.task = await push_step_output(self.task, self.queue, self.flow_state, {})
            return False, None

        return True, slot_data


    # TODO
    async def _get_last_output(self, task: TaskBlock) -> Optional[dict[str, Any]]:
        """获取上一步的输出"""
        return None


    async def _execute_call(self, call_obj: Any, *, is_final_answer: bool) -> dict[str, Any]:
        """执行Call并处理结果"""
        # call_obj一定合法；开始判断是否为最终结果
        if is_final_answer and isinstance(call_obj, LLM):
            # 最后一步 & 是大模型步骤，直接流式输出
            async for chunk in call_obj.stream():
                await push_text_output(self.task, self.queue, chunk)
                self._final_answer += chunk
            self.flow_state.status = StepStatus.SUCCESS
            return {
                "message": self._final_answer,
            }

        # 其他情况：先运行步骤，得到结果
        result: dict[str, Any] = await call_obj.exec()
        if is_final_answer:
            if call_obj.name == "Convert":
                # 如果是Convert，直接输出转换之后的结果
                self._final_answer += result["message"]
                await push_text_output(self.task, self.queue, self._final_answer)
                self.flow_state.status = StepStatus.SUCCESS
                return {
                    "message": self._final_answer,
                }
            # 其他工具，加一步大模型过程
            # FIXME: 使用单独的Prompt
            self.flow_state.status = StepStatus.SUCCESS
            return {
                "message": self._final_answer,
            }

        # 其他情况：返回结果
        self.flow_state.status = StepStatus.SUCCESS
        return result


    async def _run_step(self, step_id: str, step_data: Step) -> None:
        """运行单个步骤"""
        logger.info("[FlowExecutor] 运行步骤 %s", step_data.name)

        # State写入ID和运行状态
        self.flow_state.step_id = step_id
        self.flow_state.step_name = step_data.name
        self.flow_state.status = StepStatus.RUNNING

        # 查找下一个步骤；判断是否是end前最后一步
        next_step = await self._get_next_step()
        is_final_answer = next_step == "end"

        # 获取并验证Call类
        node_id = step_data.node
        call_cls = await self._get_call_cls(node_id)

        # 准备系统变量
        sys_vars = CallVars(
            question=self.question,
            task_id=self.task.record.task_id,
            flow_id=self.post_body_app.flow_id,
            session_id=self.task.session_id,
            history=self.task.flow_context,
            summary=self.flow_state.ai_summary,
            user_sub=self.task.user_sub,
        )

        # 初始化Call
        call_obj = call_cls.model_validate(step_data.params)
        input_data = await call_obj.init(sys_vars)

        # TODO: 处理slots
        # can_continue, slot_data = await self._process_slots(call_obj)
        # if not self._can_continue:
        #     return

        # 执行Call并获取结果
        self.task = await push_step_input(self.task, self.queue, self.flow_state, input_data)
        result_data = await self._execute_call(call_obj, is_final_answer=is_final_answer)
        self.task = await push_step_output(self.task, self.queue, self.flow_state, result_data)

        # 更新下一步
        self.flow_state.step_id = next_step


    async def _get_next_step(self) -> str:
        """在当前步骤执行前，尝试获取下一步"""
        # 如果当前步骤为结束，则直接返回
        if self.flow_state.step_id == "end" or not self.flow_state.step_id:
            # 如果是最后一步，设置停止标志
            self._can_continue = False
            return ""

        if self.flow.steps[self.flow_state.step_id].node == "Choice":
            # 如果是选择步骤，那么现在还不知道下一步是谁，直接返回
            return ""

        next_steps = []
        # 遍历Edges，查找下一个节点
        for edge in self.flow.edges:
            if edge.edge_from == self.flow_state.step_id:
                next_steps += [edge.edge_to]

        # 如果step没有任何出边，直接跳到end
        if not next_steps:
            return "end"

        # FIXME: 目前只使用第一个出边
        logger.info("[FlowExecutor] 下一步 %s", next_steps[0])
        return next_steps[0]


    async def run(self) -> None:
        """运行流，返回各步骤结果，直到无法继续执行

        数据通过向Queue发送消息的方式传输
        """
        task_actor = ray.get_actor("task")
        logger.info("[FlowExecutor] 运行工作流")
        # 推送Flow开始消息
        self.task = await push_flow_start(self.task, self.queue, self.flow_state, self.question)

        # 如果允许继续运行Flow
        while self._can_continue:
            # Flow定义中找不到step
            if not self.flow_state.step_id or (self.flow_state.step_id not in self.flow.steps):
                logger.error("[FlowExecutor] 当前步骤 %s 不存在", self.flow_state.step_id)
                self.flow_state.status = StepStatus.ERROR

            if self.flow_state.status == StepStatus.ERROR:
                # 执行错误处理步骤
                logger.warning("[FlowExecutor] Executor出错，执行错误处理步骤")
                step = self.flow.on_error
                await self._run_error(step)
            else:
                # 执行正常步骤
                step = self.flow.steps[self.flow_state.step_id]
                await self._run_step(self.flow_state.step_id, step)

            # 步骤结束，更新全局的Task
            await task_actor.set_task.remote(self.task.record.task_id, self.task)

        # 推送Flow停止消息
        self.task = await push_flow_stop(self.task, self.queue, self.flow_state, self.flow, self._final_answer)

        # 更新全局的Task
        await task_actor.set_task.remote(self.task.record.task_id, self.task)
