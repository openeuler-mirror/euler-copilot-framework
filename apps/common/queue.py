"""消息队列模块"""
import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

from redis.exceptions import ResponseError

from apps.constants import LOGGER
from apps.entities.enum_var import EventType, StepStatus
from apps.entities.message import (
    HeartbeatData,
    MessageBase,
    MessageFlow,
    MessageMetadata,
)
from apps.entities.task import TaskBlock
from apps.manager.task import TaskManager
from apps.models.redis import RedisConnectionPool


class MessageQueue:
    """包装SimpleQueue，加入组装消息、自动心跳等机制"""

    _heartbeat_interval: float = 3.0


    async def init(self, task_id: str, *, enable_heartbeat: bool = False) -> None:
        """异步初始化消息队列

        :param task_id: 任务ID
        :param enable_heartbeat: 是否开启自动心跳机制
        """
        self._task_id = task_id
        self._stream_name = f"TaskMq_{task_id}"
        self._group_name = f"TaskMq_{task_id}_group"
        self._consumer_name = "consumer"
        self._close = False

        if enable_heartbeat:
            self._heartbeat_task = asyncio.create_task(self._heartbeat())


    async def push_output(self, event_type: EventType, data: dict[str, Any]) -> None:
        """组装用于向用户（前端/Shell端）输出的消息"""
        client = RedisConnectionPool.get_redis_connection()

        if event_type == EventType.DONE:
            await client.publish(self._stream_name, "[DONE]")
            return

        tcb: TaskBlock = await TaskManager.get_task(self._task_id)

        # 计算创建Task到现在的时间
        used_time = round((datetime.now(timezone.utc).timestamp() - tcb.record.metadata.time), 2)
        metadata = MessageMetadata(
            time=used_time,
            input_tokens=tcb.record.metadata.input_tokens,
            output_tokens=tcb.record.metadata.output_tokens,
        )

        if tcb.flow_state:
            history_ids = tcb.new_context
            if not history_ids:
                # 如果new_history为空，则说明是第一次执行，创建一个空值
                flow = MessageFlow(
                    plugin_id=tcb.flow_state.plugin_id,
                    flow_id=tcb.flow_state.name,
                    step_name="start",
                    step_status=StepStatus.RUNNING,
                    step_progress="",
                )
            else:
                # 如果new_history不为空，则说明是继续执行，使用最后一个FlowHistory
                history = tcb.flow_context[tcb.flow_state.step_name]

                flow = MessageFlow(
                    plugin_id=history.plugin_id,
                    flow_id=history.flow_id,
                    step_name=history.step_name,
                    step_status=history.status,
                    step_progress=history.step_order,
                )
        else:
            flow = None

        message = MessageBase(
            event=event_type,
            id=tcb.record.id,
            group_id=tcb.record.group_id,
            conversation_id=tcb.record.conversation_id,
            task_id=tcb.record.task_id,
            metadata=metadata,
            flow=flow,
            content=data,
        )

        while True:
            try:
                group_info = await client.xinfo_groups(self._stream_name)
                if not group_info[0]["pending"]:
                    break
                await asyncio.sleep(0.1)
            except Exception as e:
                LOGGER.error(f"[Queue] Get group info failed: {e}")
                break

        await client.xadd(self._stream_name, {"data": json.dumps(message.model_dump(by_alias=True, exclude_none=True), ensure_ascii=False)})


    async def get(self) -> AsyncGenerator[str, None]:
        """从Queue中获取消息；变为async generator"""
        client = RedisConnectionPool.get_redis_connection()

        try:
            await client.xgroup_create(self._stream_name, self._group_name, id="0", mkstream=True)
        except ResponseError:
            LOGGER.warning(f"[Queue] Task {self._task_id} group {self._group_name} already exists.")

        while True:
            if self._close:
                # 注意：这里进行实际的关闭操作
                await client.xgroup_destroy(self._stream_name, self._group_name)
                await client.delete(self._stream_name)
                break

            # 获取消息
            message = await client.xreadgroup(self._group_name, self._consumer_name, streams={self._stream_name: ">"}, count=1, block=1000)
            # 检查消息是否合法
            if not message:
                continue

            # 获取消息ID和消息
            message_id, message = message[0][1][0]
            if message and isinstance(message, dict):
                yield message[b"data"].decode("utf-8")
                await client.xack(self._stream_name, self._group_name, message_id)


    async def _heartbeat(self) -> None:
        """组装用于向用户（前端/Shell端）输出的心跳"""
        heartbeat_template = HeartbeatData()
        heartbeat_msg = json.dumps(heartbeat_template.model_dump(by_alias=True), ensure_ascii=False)
        client = RedisConnectionPool.get_redis_connection()

        while True:
            # 如果关闭，则停止心跳
            if self._close:
                break

            # 等待一个间隔
            await asyncio.sleep(self._heartbeat_interval)

            # 查看是否已清空REL
            group_info = await client.xinfo_groups(self._stream_name)
            if group_info[0]["pending"]:
                continue

            # 添加心跳消息，得到ID
            await client.xadd(self._stream_name, {"data": heartbeat_msg})


    async def close(self) -> None:
        """关闭消息队列"""
        self._close = True
