"""Flow执行Executor

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import traceback
from typing import Any

import ray
from pydantic import BaseModel, Field

from apps.constants import LOGGER, STEP_HISTORY_SIZE
from apps.entities.enum_var import StepStatus
from apps.entities.flow import Flow, Step
from apps.entities.request_data import RequestDataApp
from apps.entities.scheduler import CallVars
from apps.entities.task import ExecutorState, TaskBlock
from apps.llm.patterns import ExecutorThought
from apps.llm.patterns.executor import ExecutorBackground
from apps.manager.node import NodeManager
from apps.manager.task import TaskManager
from apps.scheduler.executor.message import (
    push_flow_start,
    push_flow_stop,
    push_step_input,
    push_step_output,
)
from apps.scheduler.slot.slot import Slot


# 单个流的执行工具
class Executor(BaseModel):
    """用于执行工作流的Executor"""

    name: str = Field(description="Flow名称")
    description: str = Field(description="Flow描述")

    flow: Flow = Field(description="工作流数据")
    task: TaskBlock = Field(description="任务信息")
    queue: ray.ObjectRef = Field(description="消息队列")
    question: str = Field(description="用户输入")
    context: str = Field(description="上下文", default="")
    post_body_app: RequestDataApp = Field(description="请求体中的app信息")

    class Config:
        """Pydantic配置"""

        arbitrary_types_allowed = True


    async def load_state(self) -> None:
        """从数据库中加载FlowExecutor的状态"""
        # 尝试恢复State
        if self.task.flow_state:
            self.flow_state = self.task.flow_state
            # 如果flow_context为空，则从flow_history中恢复
            if not self.task.flow_context:
                self.task.flow_context = await TaskManager.get_flow_history_by_task_id(self.task.record.task_id)
            self.task.new_context = []
        else:
            # 创建ExecutorState
            self.flow_state = ExecutorState(
                name=str(self.flow.name),
                description=str(self.flow.description),
                status=StepStatus.RUNNING,
                app_id=str(self.post_body_app.app_id),
                step_id="start",
                thought="",
                filled_data=self.post_body_app.params,
            )
        # 是否结束运行
        self._stop = False


    async def _check_cls(self, call_cls: Any) -> bool:
        """检查Call是否符合标准要求"""
        flag = True
        if not hasattr(call_cls, "name") or not isinstance(call_cls.name, str):
            flag = False
        if not hasattr(call_cls, "description") or not isinstance(call_cls.description, str):
            flag = False
        if not hasattr(call_cls, "exec") or not callable(call_cls.exec):
            flag = False
        return flag


    async def _run_step(self, step_data: Step) -> dict[str, Any]:
        """运行单个步骤"""
        # 更新State
        self.flow_state.step_id = step_data.name
        self.flow_state.status = StepStatus.RUNNING

        # Call类型为none，跳过执行
        node_id = step_data.node
        if node_id == "none":
            return {}

        # 获取对应Node的call_id
        try:
            call_id = await NodeManager.get_node_call_id(node_id)
        except Exception as e:
            LOGGER.error(f"[FlowExecutor] 获取工具{node_id}的call_id时发生错误：{e}。\n{traceback.format_exc()}")
            self.flow_state.status = StepStatus.ERROR
            return {}

        # 从Pool中获取对应的Call
        pool = ray.get_actor("pool")
        try:
            call_cls = await pool.get_call.remote(call_id, self.flow_state.app_id)
        except Exception as e:
            LOGGER.error(f"[FlowExecutor] 载入工具{node_id}时发生错误：{e}。\n{traceback.format_exc()}")
            self.flow_state.status = StepStatus.ERROR
            return {}

        # 检查Call合法性
        if not self._check_cls(call_cls):
            LOGGER.error(f"[FlowExecutor] 工具{node_id}不符合Call标准要求。")
            self.flow_state.status = StepStatus.ERROR
            return {}

        # 准备history
        history = list(self.task.flow_context.values())
        length = min(STEP_HISTORY_SIZE, len(history))
        history = history[-length:]

        # 准备SysCallVars
        sys_vars = CallVars(
            question=self.question,
            task_id=self.task.record.task_id,
            session_id=self.task.session_id,
            extra={
                "app_id": self.flow_state.app_id,
                "flow_id": self.flow_state.name,
            },
            history=history,
            background=self.flow_state.thought,
        )

        # 初始化Call
        try:
            # 拿到开发者定义的参数
            params = step_data.params
            # 初始化Call
            call_obj = call_cls(sys_vars, **params)
        except Exception as e:
            err = f"[FlowExecutor] 初始化工具{node_id}时发生错误：{e!s}\n{traceback.format_exc()}"
            LOGGER.error(err)
            self.flow_state.status = StepStatus.ERROR
            return {}

        # 如果call_obj里面有slot_schema，初始化Slot处理器
        if hasattr(call_obj, "slot_schema") and call_obj.slot_schema:
            slot_processor = Slot(call_obj.slot_schema)
        else:
            # 没有schema，不进行处理
            slot_processor = None

        if slot_processor is not None:
            # 处理参数
            remaining_schema, slot_data = await slot_processor.process(
                self.flow_state.filled_data,
                self.sysexec_vars.app_data.params,
                {
                    "task_id": self.task.record.task_id,
                    "question": self.question,
                    "thought": self.flow_state.thought,
                    "previous_output": await self._get_last_output(self.task),
                },
            )
            # 保存Schema至State
            self.flow_state.remaining_schema = remaining_schema
            self.flow_state.filled_data.update(slot_data)
            # 如果还有未填充的部分，则终止执行
            if remaining_schema:
                self._stop = True
                self.flow_state.status = StepStatus.RUNNING
                # 推送空输入
                await push_step_input(self.task, self.queue, self.flow_state, self.flow)
                # 推送空输出
                self.flow_state.status = StepStatus.PARAM
                result = {}
                await push_step_output(self.task, self.queue, self.flow_state, result)
                return result

        # 推送步骤输入
        await push_step_input(self._vars.task_id, self._vars.queue, self.flow_state, self._flow_data)

        # 执行Call
        try:
            result: dict[str, Any] = await call_obj.call(self.flow_state.filled_data)
        except Exception as e:
            err = f"[FlowExecutor] 执行工具{node_id}时发生错误：{e!s}\n{traceback.format_exc()}"
            LOGGER.error(err)
            self.flow_state.status = StepStatus.ERROR
            # 推送空输出
            result = {}
            await push_step_output(self._vars.task_id, self._vars.queue, self.flow_state, self._flow_data, result)
            return result

        # 更新背景
        await self._update_thought(call_obj.name, call_obj.description, result)
        # 推送消息、保存结果
        self.flow_state.status = StepStatus.SUCCESS
        await push_step_output(self._vars.task_id, self._vars.queue, self.flow_state, self._flow_data, result)
        return result


    async def _handle_next_step(self, result: dict[str, Any]) -> None:
        """处理下一步"""
        if self._next_step is None:
            return

        # 处理分支（cloice工具）
        if self._flow_data.steps[self._next_step].call_type == "cloice" and result.extra is not None:
            self._next_step = result.extra.get("next_step")
            return

        # 处理下一步
        self._next_step = self._flow_data.steps[self._next_step].next


    async def _update_thought(self, call_name: str, call_description: str, call_result: dict[str, Any]) -> None:
        """执行步骤后，更新FlowExecutor的思考内容"""
        # 组装工具信息
        tool_info = {
            "name": call_name,
            "description": call_description,
            "output": call_result,
        }
        # 更新背景
        self.flow_state.thought = await ExecutorThought().generate(
            self._vars.task_id,
            last_thought=self.flow_state.thought,
            user_question=self._vars.question,
            tool_info=tool_info,
        )


    async def run(self) -> None:
        """运行流，返回各步骤结果，直到无法继续执行

        数据通过向Queue发送消息的方式传输
        """
        # 推送Flow开始
        await push_flow_start(self._task, self._vars.queue, self.flow_state, self._vars.question)

        # 更新背景
        self.flow_state.thought = await ExecutorBackground().generate(self._vars.task_id, background=self._vars.background)

        while not self._stop:
            # 当前步骤不存在
            if self.flow_state.step_id not in self._flow_data.steps:
                break

            if self.flow_state.status == StepStatus.ERROR:
                # 当前步骤为错误处理步骤
                step = self._flow_data.on_error
            else:
                step = self._flow_data.steps[self.flow_state.step_id]

            # 当前步骤空白
            if not step:
                break

            # 判断当前是否为最后一步
            if step.name == "end":
                self._stop = True
            if not step.next or step.next == "end":
                self._stop = True

            # 运行步骤
            result = await self._run_step(step)

            # 如果停止，则结束执行
            if self._stop:
                break

            # 处理下一步
            await self._handle_next_step(result)

        # Flow停止运行，推送消息
        await push_flow_stop(self._vars.task_id, self._vars.queue, self.flow_state, self._flow_data, self._vars.question)
