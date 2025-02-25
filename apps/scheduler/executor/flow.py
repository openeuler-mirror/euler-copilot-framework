"""Flow执行Executor

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import traceback
from typing import Any, Optional

import ray
from pydantic import BaseModel, Field

from apps.constants import LOGGER, STEP_HISTORY_SIZE
from apps.entities.enum_var import StepStatus
from apps.entities.flow import Flow, FlowError, Step
from apps.entities.request_data import RequestDataApp
from apps.entities.scheduler import CallVars, ExecutorBackground
from apps.entities.task import ExecutorState, TaskBlock
from apps.llm.patterns.executor import ExecutorSummary
from apps.manager.node import NodeManager
from apps.manager.task import TaskManager
from apps.scheduler.call.core import CoreCall
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
    executor_background: ExecutorBackground = Field(description="Executor的背景信息")

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
                ai_summary="",
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


    async def _run_error(self, step: FlowError) -> dict[str, Any]:
        """运行错误处理步骤"""
        pass


    async def _get_call_cls(self, node_id: str) -> Optional[type[CoreCall]]:
        """获取并验证Call类"""
        # 获取对应Node的call_id
        try:
            call_id = await NodeManager.get_node_call_id(node_id)
        except Exception as e:
            LOGGER.error(f"[FlowExecutor] 获取工具{node_id}的call_id时发生错误：{e}。\n{traceback.format_exc()}")
            self.flow_state.status = StepStatus.ERROR
            return None

        # 从Pool中获取对应的Call
        pool = ray.get_actor("pool")
        try:
            call_cls: type[CoreCall] = await pool.get_call.remote(call_id, self.flow_state.app_id)
        except Exception as e:
            LOGGER.error(f"[FlowExecutor] 载入工具{node_id}时发生错误：{e}。\n{traceback.format_exc()}")
            self.flow_state.status = StepStatus.ERROR
            return None

        # 检查Call合法性
        if not self._check_cls(call_cls):
            LOGGER.error(f"[FlowExecutor] 工具{node_id}不符合Call标准要求。")
            self.flow_state.status = StepStatus.ERROR
            return None

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
            self._stop = True
            self.flow_state.status = StepStatus.RUNNING
            # 推送空输入输出
            await push_step_input(self.task.record.task_id, self.queue, self.flow_state, self.flow)
            self.flow_state.status = StepStatus.PARAM
            await push_step_output(self.task.record.task_id, self.queue, self.flow_state, {})
            return False, None

        return True, slot_data


    async def _execute_call(self, call_obj: Any, sys_vars: CallVars, node_id: str) -> dict[str, Any]:
        """执行Call并处理结果"""
        if not call_obj:
            LOGGER.error(f"[FlowExecutor] 工具{node_id}不存在。")
            return {}

        try:
            result: BaseModel = await call_obj(sys_vars)
        except Exception as e:
            LOGGER.error(f"[FlowExecutor] 执行工具{node_id}时发生错误：{e!s}\n{traceback.format_exc()}")
            self.flow_state.status = StepStatus.ERROR
            return {}

        try:
            result_data = result.model_dump(exclude_none=True, by_alias=True)
        except Exception as e:
            LOGGER.error(f"[FlowExecutor] 无法处理工具{node_id}返回值：{e!s}\n{traceback.format_exc()}")
            self.flow_state.status = StepStatus.ERROR
            return {}

        self.flow_state.status = StepStatus.SUCCESS
        return result_data


    async def _run_step(self, step_data: Step) -> None:
        """运行单个步骤"""
        # 更新State
        self.flow_state.step_id = step_data.name
        self.flow_state.status = StepStatus.RUNNING

        # Call类型为none，跳过执行
        node_id = step_data.node
        if node_id == "none":
            return

        # 获取并验证Call类
        call_cls = await self._get_call_cls(node_id)
        if call_cls is None:
            return

        # 准备系统变量
        history = list(self.task.flow_context.values())[-STEP_HISTORY_SIZE:]
        sys_vars = CallVars(
            question=self.question,
            task_id=self.task.record.task_id,
            flow_id=self.post_body_app.flow_id,
            session_id=self.task.session_id,
            history=history,
            background=self.flow_state.ai_summary,
        )

        # 初始化Call
        try:
            call_obj = call_cls.model_validate(step_data.params)
        except Exception as e:
            err = f"[FlowExecutor] 初始化工具{node_id}时发生错误：{e!s}\n{traceback.format_exc()}"
            LOGGER.error(err)
            self.flow_state.status = StepStatus.ERROR
            return

        # TODO: 处理slots
        # can_continue, slot_data = await self._process_slots(call_obj)
        # if not can_continue:
        #     return

        # 推送步骤输入
        await push_step_input(self.task.record.task_id, self.queue, self.flow_state, self.flow_state.filled_data)

        # 执行Call并获取结果
        result_data = await self._execute_call(call_obj, sys_vars, node_id)

        # 推送输出
        await push_step_output(self.task.record.task_id, self.queue, self.flow_state, result_data)
        return


    async def _handle_next_step(self) -> None:
        """处理下一步"""
        next_nodes = []
        # 遍历Edges，查找下一个节点
        for edge in self.flow.edges:
            if edge.edge_from == self.flow_state.step_id:
                next_nodes += [edge.edge_to]

        # TODO
        # 处理分支（cloice工具）
        # if self._flow_data.steps[self._next_step].call_type == "choice" and result.extra is not None:
        #     self._next_step = result.extra.get("next_step")
        #     return

        # 处理下一步
        if not next_nodes:
            self.flow_state.step_id = "end"
        else:
            self.flow_state.step_id = next_nodes[0]


    async def run(self) -> None:
        """运行流，返回各步骤结果，直到无法继续执行

        数据通过向Queue发送消息的方式传输
        """
        # 推送Flow开始
        await push_flow_start(self.task.record.task_id, self.queue, self.flow_state, self.question)

        while not self._stop:
            # 当前步骤不存在
            if self.flow_state.step_id not in self.flow.steps:
                break

            if self.flow_state.status == StepStatus.ERROR:
                # 当前步骤为错误处理步骤
                step = self.flow.on_error
            else:
                step = self.flow.steps[self.flow_state.step_id]

            # 当前步骤空白
            if not step:
                break

            # 判断当前是否为最后一步
            if self.flow_state.step_id == "end":
                break

            # 运行步骤
            if isinstance(step, FlowError):
                result = await self._run_error(step)
            else:
                result = await self._run_step(step)

            # 如果停止，则结束执行
            if self._stop:
                break

            # 处理下一步
            await self._handle_next_step()

        # Flow停止运行，推送消息
        await push_flow_stop(self.task.record.task_id, self.queue, self.flow_state, self.flow)
