"""消息队列模块"""
import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import ray
from redis.exceptions import ResponseError

from apps.entities.enum_var import EventType
from apps.entities.message import (
    HeartbeatData,
    MessageBase,
    MessageFlow,
    MessageMetadata,
)
from apps.entities.task import TaskBlock
from apps.models.redis import RedisConnectionPool

logger = logging.getLogger(__name__)

@ray.remote
class MessageQueue:
    """包装SimpleQueue，加入组装消息、自动心跳等机制"""

    _heartbeat_interval: float = 3.0


    async def init(self, task_id: str) -> None:
        """异步初始化消息队列

        :param task_id: 任务ID
        :param enable_heartbeat: 是否开启自动心跳机制
        """
        self._task_id = task_id
        self._stream_name = f"TaskMq_{task_id}"
        self._group_name = f"TaskMq_{task_id}_group"
        self._consumer_name = "consumer"
        self._close = False

        self._heartbeat_task = asyncio.get_running_loop().create_task(self._heartbeat())


    async def push_output(self, task: TaskBlock, event_type: EventType, data: dict[str, Any]) -> None:
        """组装用于向用户（前端/Shell端）输出的消息"""
        client = RedisConnectionPool.get_redis_connection()

        if event_type == EventType.DONE:
            await client.publish(self._stream_name, "[DONE]")
            return

        # 计算当前Step时间
        step_time = round((datetime.now(timezone.utc).timestamp() - task.record.metadata.time), 3)
        metadata = MessageMetadata(
            time=step_time,
            input_tokens=task.record.metadata.input_tokens,
            output_tokens=task.record.metadata.output_tokens,
        )

        if task.flow_state:
            # 如果使用了Flow
            flow = MessageFlow(
                appId=task.flow_state.app_id,
                flowId=task.flow_state.name,
                stepId=task.flow_state.step_id,
                stepStatus=task.flow_state.status,
            )
        else:
            flow = None

        message = MessageBase(
            event=event_type,
            id=task.record.id,
            groupId=task.record.group_id,
            conversationId=task.record.conversation_id,
            taskId=task.record.task_id,
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
            except Exception:
                logger.exception("[Queue] 获取组信息失败")
                break

        await client.xadd(self._stream_name, {"data": json.dumps(message.model_dump(by_alias=True, exclude_none=True), ensure_ascii=False)})


    async def get(self) -> AsyncGenerator[str, None]:
        """从Queue中获取消息；变为async generator"""
        client = RedisConnectionPool.get_redis_connection()

        try:
            await client.xgroup_create(self._stream_name, self._group_name, id="0", mkstream=True)
        except ResponseError:
            logger.warning("[Queue] 任务 %s 组 %s 已存在", self._task_id, self._group_name)

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
            try:
                group_info = await client.xinfo_groups(self._stream_name)
                if group_info[0]["pending"]:
                    continue
            except Exception:
                logger.info("[Queue] Redis流已结束")
                break

            # 添加心跳消息，得到ID
            await client.xadd(self._stream_name, {"data": heartbeat_msg})


    async def close(self) -> None:
        """关闭消息队列"""
        self._close = True
