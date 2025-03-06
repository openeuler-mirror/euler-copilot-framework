"""FlowExecutor的消息推送

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from datetime import datetime, timezone
from typing import Any

from ray import actor

from apps.entities.enum_var import EventType, FlowOutputType
from apps.entities.flow import Flow
from apps.entities.message import (
    FlowStartContent,
    FlowStopContent,
    TextAddContent,
)
from apps.entities.task import (
    ExecutorState,
    FlowStepHistory,
    TaskBlock,
)


# FIXME: 临时使用截断规避前端问题
def truncate_data(data: Any) -> Any:
    """截断数据"""
    if isinstance(data, dict):
        return {k: truncate_data(v) for k, v in data.items()}
    if isinstance(data, list):
        return [truncate_data(v) for v in data]
    if isinstance(data, str):
        if len(data) > 300:
            return data[:300] + "..."
        return data
    return data


async def push_step_input(task: TaskBlock, queue: actor.ActorHandle, state: ExecutorState, input_data: dict[str, Any]) -> TaskBlock:
    """推送步骤输入"""
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
    # 步骤开始，重置时间
    task.record.metadata.time_cost = round(datetime.now(timezone.utc).timestamp(), 2)

    # 推送消息
    await queue.push_output.remote(task, event_type=EventType.STEP_INPUT, data=truncate_data(input_data)) # type: ignore[attr-defined]
    return task


async def push_step_output(task: TaskBlock, queue: actor.ActorHandle, state: ExecutorState, output: dict[str, Any]) -> TaskBlock:
    """推送步骤输出"""
    # 更新State
    task.flow_state = state

    # 更新FlowContext
    task.flow_context[state.step_id].output_data = output
    task.flow_context[state.step_id].status = state.status

    # FlowContext加入Record
    task.new_context.append(task.flow_context[state.step_id].id)

    # 推送消息
    await queue.push_output.remote(task, event_type=EventType.STEP_OUTPUT, data=truncate_data(output)) # type: ignore[attr-defined]
    return task


async def push_flow_start(task: TaskBlock, queue: actor.ActorHandle, state: ExecutorState, question: str) -> TaskBlock:
    """推送Flow开始"""
    # 设置state
    task.flow_state = state

    # 组装消息
    content = FlowStartContent(
        question=question,
        params=state.filled_data,
    )
    # 推送消息
    await queue.push_output.remote(task, event_type=EventType.FLOW_START, data=content.model_dump(exclude_none=True, by_alias=True)) # type: ignore[attr-defined]
    return task


async def assemble_flow_stop_content(state: ExecutorState, flow: Flow) -> FlowStopContent:
    """组装Flow结束消息"""
    if state.remaining_schema:
        # 如果当前Flow是填充步骤，则推送Schema
        content = FlowStopContent(
            type=FlowOutputType.SCHEMA,
            data=state.remaining_schema,
        )
    else:
        content = FlowStopContent()

    return content

    # elif call_type == "render":
    #     # 如果当前Flow是图表，则推送Chart
    #     chart_option = task.flow_context[state.step_id].output_data["output"]
    #     content = FlowStopContent(
    #         type=FlowOutputType.CHART,
    #         data=chart_option,
    #     )

async def push_flow_stop(task: TaskBlock, queue: actor.ActorHandle, state: ExecutorState, flow: Flow, final_answer: str) -> TaskBlock:
    """推送Flow结束"""
    # 设置state
    task.flow_state = state
    # 保存最终输出
    task.record.content.answer = final_answer
    content = await assemble_flow_stop_content(state, flow)

    # 推送Stop消息
    await queue.push_output.remote(task, event_type=EventType.FLOW_STOP, data=content.model_dump(exclude_none=True, by_alias=True)) # type: ignore[attr-defined]
    return task


async def push_text_output(task: TaskBlock, queue: actor.ActorHandle, text: str) -> None:
    """推送文本输出"""
    content = TextAddContent(
        text=text,
    )
    # 推送消息
    await queue.push_output.remote(task, event_type=EventType.TEXT_ADD, data=content.model_dump(exclude_none=True, by_alias=True)) # type: ignore[attr-defined]
