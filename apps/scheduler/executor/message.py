"""FlowExecutor的消息推送

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

import ray

from apps.entities.enum_var import EventType, FlowOutputType, StepStatus
from apps.entities.flow import Flow
from apps.entities.message import (
    FlowStartContent,
    FlowStopContent,
)
from apps.entities.task import ExecutorState, FlowStepHistory, TaskBlock


async def push_step_input(task_id: str, queue: ray.ObjectRef, state: ExecutorState, input_data: dict[str, Any]) -> None:
    """推送步骤输入"""
    task_actor = ray.get_actor("task")
    task: TaskBlock = await task_actor.get_task.remote(task_id)
    # 更新State
    task.flow_state = state
    # 更新FlowContext
    task.flow_context[state.step_id] = FlowStepHistory(
        task_id=task.record.task_id,
        flow_id=state.name,
        step_id=state.step_id,
        status=state.status,
        input_data=state.filled_data,
        output_data={},
    )

    # 推送消息
    await queue.push_output.remote(task, event_type=EventType.STEP_INPUT, data=input_data) # type: ignore[attr-defined]
    await task_actor.set_task.remote(task_id, task)


async def push_step_output(task_id: str, queue: ray.ObjectRef, state: ExecutorState, output: dict[str, Any]) -> None:
    """推送步骤输出"""
    task_actor = ray.get_actor("task")
    task: TaskBlock = await task_actor.get_task.remote(task_id)
    # 更新State
    task.flow_state = state

    # 更新FlowContext
    task.flow_context[state.step_id].output_data = output
    task.flow_context[state.step_id].status = state.status

    # FlowContext加入Record
    task.new_context.append(task.flow_context[state.step_id].id)

    # 推送消息
    await queue.push_output.remote(task, event_type=EventType.STEP_OUTPUT, data=output) # type: ignore[attr-defined]
    await task_actor.set_task.remote(task_id, task)


async def push_flow_start(task_id: str, queue: ray.ObjectRef, state: ExecutorState, question: str) -> None:
    """推送Flow开始"""
    task_actor = ray.get_actor("task")
    task: TaskBlock = await task_actor.get_task.remote(task_id)
    # 设置state
    task.flow_state = state

    # 组装消息
    content = FlowStartContent(
        question=question,
        params=state.filled_data,
    )
    # 推送消息
    await queue.push_output.remote(task, event_type=EventType.FLOW_START, data=content.model_dump(exclude_none=True, by_alias=True)) # type: ignore[attr-defined]
    await task_actor.set_task.remote(task_id, task)


async def assemble_flow_stop_content(state: ExecutorState, flow: Flow) -> FlowStopContent:
    """组装Flow结束消息"""
    call_type = flow.steps[state.step_id].call_type
    if state.remaining_schema:
        # 如果当前Flow是填充步骤，则推送Schema
        content = FlowStopContent(
            type=FlowOutputType.SCHEMA,
            data=state.remaining_schema,
        )
    elif call_type == "render":
        # 如果当前Flow是图表，则推送Chart
        chart_option = task.flow_context[state.step_id].output_data["output"]
        content = FlowStopContent(
            type=FlowOutputType.CHART,
            data=chart_option,
        )
    else:
        # 如果当前Flow是其他类型，则推送空消息
        content = FlowStopContent()

    return content


async def push_flow_stop(task_id: str, queue: ray.ObjectRef, state: ExecutorState, flow: Flow) -> None:
    """推送Flow结束"""
    task_actor = ray.get_actor("task")
    task: TaskBlock = await task_actor.get_task.remote(task_id)
    # 设置state
    task.flow_state = state
    content = await assemble_flow_stop_content(state, flow)

    # 推送Stop消息
    await queue.push_output.remote(task, event_type=EventType.FLOW_STOP, data=content.model_dump(exclude_none=True, by_alias=True)) # type: ignore[attr-defined]
    await task_actor.set_task.remote(task_id, task)
