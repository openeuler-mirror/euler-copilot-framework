"""Flow执行Executor

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import traceback
from typing import Optional

from apps.constants import LOGGER, MAX_SCHEDULER_HISTORY_SIZE
from apps.entities.enum_var import StepStatus
from apps.entities.flow import Step
from apps.entities.scheduler import (
    SysCallVars,
    SysExecVars,
)
from apps.entities.task import ExecutorState, TaskBlock
from apps.llm.patterns import ExecutorThought
from apps.llm.patterns.executor import ExecutorBackground
from apps.manager import TaskManager
from apps.scheduler.executor.message import (
    push_flow_start,
    push_flow_stop,
    push_step_input,
    push_step_output,
)
from apps.scheduler.pool.pool import Pool
from apps.scheduler.slot.slot import Slot


# 单个流的执行工具
class Executor:
    """用于执行工作流的Executor"""

    name: str = ""
    """Flow名称"""
    description: str = ""
    """Flow描述"""


    async def load_state(self, sysexec_vars: SysExecVars) -> None:
        """从JSON中加载FlowExecutor的状态"""
        # 获取Task
        task = await TaskManager.get_task(sysexec_vars.task_id)
        if not task:
            err = "[Executor] Task error."
            raise ValueError(err)

        # 加载Flow信息
        flow, flow_data = Pool().get_flow(sysexec_vars.plugin_data.flow_id, sysexec_vars.plugin_data.plugin_id)
        # Flow不合法，拒绝执行
        if flow is None or flow_data is None:
            err = "Flow不合法！"
            raise ValueError(err)

        # 设置名称和描述
        self.name = str(flow.name)
        self.description = str(flow.description)

        # 保存当前变量（只读）
        self._vars = sysexec_vars
        # 保存Flow数据（只读）
        self._flow_data = flow_data

        # 尝试恢复State
        if task.flow_state:
            self.flow_state = task.flow_state
            # 如果flow_context为空，则从flow_history中恢复
            if not task.flow_context:
                task.flow_context = await TaskManager.get_flow_history_by_task_id(self._vars.task_id)
            task.new_context = []
        else:
            # 创建ExecutorState
            self.flow_state = ExecutorState(
                name=str(flow.name),
                description=str(flow.description),
                status=StepStatus.RUNNING,
                plugin_id=str(sysexec_vars.plugin_data.plugin_id),
                step_id="start",
                thought="",
                slot_data=sysexec_vars.plugin_data.params,
            )
        # 是否结束运行
        self._stop = False
        await TaskManager.set_task(self._vars.task_id, task)


    async def _get_last_output(self, task: TaskBlock) -> Optional[CallResult]:
        """获取上一步的输出"""
        if not task.flow_context:
            return None
        return CallResult(**task.flow_context[self.flow_state.step_id].output_data)


    async def _run_step(self, step_data: Step) -> CallResult:  # noqa: PLR0915
        """运行单个步骤"""
        # 获取Task
        task = await TaskManager.get_task(self._vars.task_id)
        if not task:
            err = "[Executor] Task error."
            raise ValueError(err)

        # 更新State
        self.flow_state.step_id = step_data.name
        self.flow_state.status = StepStatus.RUNNING

        # Call类型为none，直接错误
        call_type = step_data.call_type
        if call_type == "none":
            self.flow_state.status = StepStatus.ERROR
            return CallResult(
                message="",
                output={},
                output_schema={},
                extra=None,
            )

        # 从Pool中获取对应的Call
        call_data, call_cls = Pool().get_call(call_type, self.flow_state.plugin_id)
        if call_data is None or call_cls is None:
            err = f"[FlowExecutor] 尝试执行工具{call_type}时发生错误：找不到该工具。\n{traceback.format_exc()}"
            LOGGER.error(err)
            self.flow_state.status = StepStatus.ERROR
            return CallResult(
                message=err,
                output={},
                output_schema={},
                extra=None,
            )

        # 准备history
        history = list(task.flow_context.values())
        length = min(MAX_SCHEDULER_HISTORY_SIZE, len(history))
        history = history[-length:]

        # 准备SysCallVars
        sys_vars = SysCallVars(
            question=self._vars.question,
            task_id=self._vars.task_id,
            session_id=self._vars.session_id,
            extra={
                "plugin_id": self.flow_state.plugin_id,
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
            err = f"[FlowExecutor] 初始化工具{call_type}时发生错误：{e!s}\n{traceback.format_exc()}"
            LOGGER.error(err)
            self.flow_state.status = StepStatus.ERROR
            return CallResult(
                message=err,
                output={},
                output_schema={},
                extra=None,
            )

        # 如果call_obj里面有slot_schema，初始化Slot处理器
        if hasattr(call_obj, "slot_schema") and call_obj.slot_schema:
            slot_processor = Slot(call_obj.slot_schema)
        else:
            # 没有schema，不进行处理
            slot_processor = None

        if slot_processor is not None:
            # 处理参数
            remaining_schema, slot_data = await slot_processor.process(
                self.flow_state.slot_data,
                self._vars.plugin_data.params,
                {
                    "task_id": self._vars.task_id,
                    "question": self._vars.question,
                    "thought": self.flow_state.thought,
                    "previous_output": await self._get_last_output(task),
                },
            )
            # 保存Schema至State
            self.flow_state.remaining_schema = remaining_schema
            self.flow_state.slot_data.update(slot_data)
            # 如果还有未填充的部分，则终止执行
            if remaining_schema:
                self._stop = True
                self.flow_state.status = StepStatus.RUNNING
                # 推送空输入
                await push_step_input(self._vars.task_id, self._vars.queue, self.flow_state, self._flow_data)
                # 推送空输出
                self.flow_state.status = StepStatus.PARAM
                result = CallResult(
                    message="当前工具参数不完整！",
                    output={},
                    output_schema={},
                    extra=None,
                )
                await push_step_output(self._vars.task_id, self._vars.queue, self.flow_state, self._flow_data, result)
                return result

        # 推送步骤输入
        await push_step_input(self._vars.task_id, self._vars.queue, self.flow_state, self._flow_data)

        # 执行Call
        try:
            result: CallResult = await call_obj.call(self.flow_state.slot_data)
        except Exception as e:
            err = f"[FlowExecutor] 执行工具{call_type}时发生错误：{e!s}\n{traceback.format_exc()}"
            LOGGER.error(err)
            self.flow_state.status = StepStatus.ERROR
            # 推送空输出
            result = CallResult(
                message=err,
                output={},
                output_schema={},
                extra=None,
            )
            await push_step_output(self._vars.task_id, self._vars.queue, self.flow_state, self._flow_data, result)
            return result

        # 更新背景
        await self._update_thought(call_obj.name, call_obj.description, result)
        # 推送消息、保存结果
        self.flow_state.status = StepStatus.SUCCESS
        await push_step_output(self._vars.task_id, self._vars.queue, self.flow_state, self._flow_data, result)
        return result


    async def _handle_next_step(self, result: CallResult) -> None:
        """处理下一步"""
        if self._next_step is None:
            return

        # 处理分支（cloice工具）
        if self._flow_data.steps[self._next_step].call_type == "cloice" and result.extra is not None:
            self._next_step = result.extra.get("next_step")
            return

        # 处理下一步
        self._next_step = self._flow_data.steps[self._next_step].next


    async def _update_thought(self, call_name: str, call_description: str, call_result: CallResult) -> None:
        """执行步骤后，更新FlowExecutor的思考内容"""
        # 组装工具信息
        tool_info = {
            "name": call_name,
            "description": call_description,
            "output": call_result.output,
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
        await push_flow_start(self._vars.task_id, self._vars.queue, self.flow_state, self._vars.question)

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
