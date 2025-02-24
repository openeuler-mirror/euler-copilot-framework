"""FlowExecutor的消息推送

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

import ray

from apps.common.queue import MessageQueue
from apps.entities.enum_var import EventType, FlowOutputType, StepStatus
from apps.entities.flow import Flow
from apps.entities.message import (
    FlowStartContent,
    FlowStopContent,
    StepInputContent,
    StepOutputContent,
    TextAddContent,
)
from apps.entities.task import ExecutorState, FlowHistory, TaskBlock
from apps.llm.patterns.executor import FinalThought


async def push_step_input(task_id: str, queue: MessageQueue, state: ExecutorState, flow: Flow) -> None:
    """推送步骤输入"""
    # 获取Task
    task_actor = ray.get_actor("task")
    task = await task_actor.get_task.remote(task_id)

    if not task.flow_state:
        err = "当前Record不存在Flow信息！"
        raise ValueError(err)

    # 更新State
    task.flow_state = state
    # 更新FlowContext
    flow_history = FlowHistory(
        task_id=task_id,
        flow_id=state.name,
        step_id=state.step_id,
        status=state.status,
        input_data=state.slot_data,
        output_data={},
    )
    task.new_context.append(flow_history.id)
    task.flow_context[state.step_id] = flow_history
    # 保存Task到TaskMap
    await task.set_task.remote(task_id, task)

    # 组装消息
    if state.status == StepStatus.ERROR:
        # 如果当前步骤是错误，则推送错误步骤的输入
        if not flow.on_error:
            err = "当前步骤不存在错误处理步骤！"
            raise ValueError(err)
        content = StepInputContent(
            callType=flow.on_error,
            params=state.slot_data,
        )
    else:
        content = StepInputContent(
            callType=flow.steps[state.step_id].call_type,
            params=state.slot_data,
        )
    # 推送消息
    await queue.push_output(event_type=EventType.STEP_INPUT, data=content.model_dump(exclude_none=True, by_alias=True))


async def push_step_output(task_id: str, queue: MessageQueue, state: ExecutorState, flow: Flow, output: dict[str, Any]) -> None:
    """推送步骤输出"""
    # 获取Task
    task_actor = ray.get_actor("task")
    task = await task_actor.get_task.remote(task_id)

    if not task.flow_state:
        err = "当前Record不存在Flow信息！"
        raise ValueError(err)

    # 更新State
    task.flow_state = state

    # 更新FlowContext
    task.flow_context[state.step_id].output_data = output
    task.flow_context[state.step_id].status = state.status
    # 保存Task到TaskMap
    await task.set_task.remote(task_id, task)

    # 组装消息；只保留message和output
    content = StepOutputContent(
        callType=flow.steps[state.step_id].call_type,
        message=output["message"] if output and "message" in output else "",
        output=output["output"] if output and "output" in output else {},
    )
    await queue.push_output(event_type=EventType.STEP_OUTPUT, data=content.model_dump(exclude_none=True, by_alias=True))


async def push_flow_start(task_id: str, queue: MessageQueue, state: ExecutorState, question: str) -> None:
    """推送Flow开始"""
    # 获取Task
    task_actor = ray.get_actor("task")
    task = await task_actor.get_task.remote(task_id)

    # 设置state
    task.flow_state = state
    # 保存Task到TaskMap
    await task.set_task.remote(task_id, task)

    # 组装消息
    content = FlowStartContent(
        question=question,
        params=state.slot_data,
    )
    # 推送消息
    await queue.push_output(event_type=EventType.FLOW_START, data=content.model_dump(exclude_none=True, by_alias=True))


async def push_flow_stop(task_id: str, queue: MessageQueue, state: ExecutorState, flow: Flow, question: str) -> None:
    """推送Flow结束"""
    # 获取Task
    task_actor = ray.get_actor("task")
    task = await task_actor.get_task.remote(task_id)

    task.flow_state = state
    await task.set_task.remote(task_id, task)

    # 准备必要数据
    call_type = flow.steps[state.step_id].call_type

    if state.remaining_schema:
        # 如果当前Flow是填充步骤，则推送Schema
        content = FlowStopContent(
            type=FlowOutputType.SCHEMA,
            data=state.remaining_schema,
        ).model_dump(exclude_none=True, by_alias=True)
    elif call_type == "render":
        # 如果当前Flow是图表，则推送Chart
        chart_option = CallResult(**task.flow_context[state.step_id].output_data).output
        content = FlowStopContent(
            type=FlowOutputType.CHART,
            data=chart_option,
        ).model_dump(exclude_none=True, by_alias=True)
    else:
        # 如果当前Flow是其他类型，则推送空消息
        content = {}

    # 推送最终结果
    params = {
        "question": question,
        "thought": state.thought,
        "final_output": content,
    }
    full_text = ""
    async for chunk in FinalThought().generate(task_id, **params):
        if not chunk:
            continue
        await queue.push_output(
            event_type=EventType.TEXT_ADD,
            data=TextAddContent(text=chunk).model_dump(exclude_none=True, by_alias=True),
        )
        full_text += chunk

    # 推送Stop消息
    await queue.push_output(event_type=EventType.FLOW_STOP, data=content)

    # 更新Thought
    task.record.content.answer = full_text
    task.flow_state = state

    await task.set_task.remote(task_id, task)
