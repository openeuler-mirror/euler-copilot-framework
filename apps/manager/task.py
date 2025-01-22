"""任务模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import uuid
from asyncio import Lock
from copy import deepcopy
from datetime import datetime, timezone
from typing import ClassVar, Optional

from apps.constants import LOGGER
from apps.entities.collection import (
    RecordGroup,
)
from apps.entities.enum_var import StepStatus
from apps.entities.record import (
    RecordContent,
    RecordData,
    RecordMetadata,
)
from apps.entities.request_data import RequestData
from apps.entities.task import FlowHistory, Task, TaskBlock
from apps.manager.record import RecordManager
from apps.models.mongo import MongoDB
from apps.models.redis import RedisConnectionPool


class TaskManager:
    """保存任务信息；每一个任务关联一组队列（现阶段只有输入和输出）"""

    _connection = RedisConnectionPool.get_redis_connection()
    _task_map: ClassVar[dict[str, TaskBlock]] = {}
    _write_lock: Lock = Lock()

    @classmethod
    async def update_token_summary(cls, task_id: str, input_num: int, output_num: int) -> None:
        """更新对应task_id的Token统计数据"""
        async with cls._write_lock:
            task = cls._task_map[task_id]
            task.record.metadata.input_tokens += input_num
            task.record.metadata.output_tokens += output_num

    @staticmethod
    async def get_task_by_conversation_id(conversation_id: str) -> Optional[Task]:
        """获取对话ID的最后一条问答组关联的任务"""
        # 查询对话ID的最后一条问答组
        last_group = await RecordManager.query_record_group_by_conversation_id(conversation_id, 1)
        if not last_group or len(last_group) == 0:
            LOGGER.error(f"No record_group found for conversation {conversation_id}.")
            # 空对话或无效对话，新建Task
            return None

        last_group = last_group[0]
        task_id = last_group.task_id

        # 查询最后一条问答组关联的任务
        task_collection = MongoDB.get_collection("task")
        task = await task_collection.find_one({"_id": task_id})
        if not task:
            # 任务不存在，新建Task
            LOGGER.error(f"Task {task_id} not found.")
            return None

        task = Task.model_validate(task)
        if task.ended:
            # Task已结束，新建Task
            return None

        return task


    @staticmethod
    async def get_task_by_group_id(group_id: str, conversation_id: str) -> Optional[Task]:
        """获取组ID的最后一条问答组关联的任务"""
        task_collection = MongoDB.get_collection("task")
        record_group_collection = MongoDB.get_collection("record_group")
        try:
            record_group = await record_group_collection.find_one({"conversation_id": conversation_id, "_id": group_id})
            if not record_group:
                return None
            record_group_obj = RecordGroup.model_validate(record_group)
            task = await task_collection.find_one({"_id": record_group_obj.task_id})
            return Task.model_validate(task)
        except Exception as e:
            LOGGER.error(f"[TaskManager] Get task by group_id failed: {e}")
            return None


    @classmethod
    async def get_task(cls, task_id: Optional[str] = None, session_id: Optional[str] = None, post_body: Optional[RequestData] = None) -> TaskBlock:
        """获取任务块"""
        # 如果task_map里面已经有了，则直接返回副本
        if task_id in cls._task_map:
            return deepcopy(cls._task_map[task_id])

        # 如果task_map里面没有，则尝试从数据库中读取
        if not session_id or not post_body:
            err = "session_id and conversation_id or group_id and conversation_id are required to recover/create a task."
            raise ValueError(err)

        if post_body.group_id:
            task = await TaskManager.get_task_by_group_id(post_body.group_id, post_body.conversation_id)
        else:
            task = await TaskManager.get_task_by_conversation_id(post_body.conversation_id)

        # 创建新的Record，缺失的数据延迟关联
        new_record = RecordData(
            id=str(uuid.uuid4()),
            conversationId=post_body.conversation_id,
            groupId=str(uuid.uuid4()) if not post_body.group_id else post_body.group_id,
            taskId="",
            content=RecordContent(
                question=post_body.question,
                answer="",
            ),
            metadata=RecordMetadata(
                input_tokens=0,
                output_tokens=0,
                time=0,
                feature=post_body.features.model_dump(by_alias=True),
            ),
            createdAt=round(datetime.now(timezone.utc).timestamp(), 3),
        )

        if not task:
            # 任务不存在，新建Task，并放入task_map
            task_id = str(uuid.uuid4())
            new_record.task_id = task_id

            async with cls._write_lock:
                cls._task_map[task_id] = TaskBlock(
                    session_id=session_id,
                    record=new_record,
                )
            return deepcopy(cls._task_map[task_id])

        # 任务存在，整理Task，放入task_map
        task_id = task.id
        new_record.task_id = task_id
        async with cls._write_lock:
            cls._task_map[task_id] = TaskBlock(
                session_id=session_id,
                record=new_record,
                flow_state=task.state,
            )

        return deepcopy(cls._task_map[task_id])

    @classmethod
    async def set_task(cls, task_id: str, value: TaskBlock) -> None:
        """设置任务块"""
        # 检查task_id合法性
        if task_id not in cls._task_map:
            err = f"Task {task_id} not found"
            raise KeyError(err)

        # 替换task_map中的数据
        async with cls._write_lock:
            cls._task_map[task_id] = value

    @classmethod
    async def save_task(cls, task_id: str) -> None:
        """保存任务块"""
        # 整理任务信息
        origin_task = await cls.get_task_by_conversation_id(cls._task_map[task_id].record.conversation_id)
        if not origin_task:
            # 创建新的Task记录
            task = Task(
                _id=task_id,
                conversation_id=cls._task_map[task_id].record.conversation_id,
                record_groups=[cls._task_map[task_id].record.group_id],
                state=cls._task_map[task_id].flow_state,
                ended=False,
                updated_at=round(datetime.now(timezone.utc).timestamp(), 3),
            )
        else:
            # 更新已有的Task记录
            task = origin_task
            task.record_groups.append(cls._task_map[task_id].record.group_id)
            task.state = cls._task_map[task_id].flow_state
            task.updated_at = round(datetime.now(timezone.utc).timestamp(), 3)

        # 判断Task是否结束
        if (
            not cls._task_map[task_id].flow_state or
            cls._task_map[task_id].flow_state.status == StepStatus.ERROR or # type: ignore[attr-defined]
            cls._task_map[task_id].flow_state.status == StepStatus.SUCCESS # type: ignore[attr-defined]
        ):
            task.ended = True

        # 使用MongoDB保存任务块
        task_collection = MongoDB.get_collection("task")

        if task_id not in cls._task_map:
            err = f"Task {task_id} not found"
            raise ValueError(err)

        await task_collection.update_one({"_id": task_id}, {"$set": task.model_dump(by_alias=True)}, upsert=True)

        # 从task_map中删除任务块，释放内存
        async with cls._write_lock:
            del cls._task_map[task_id]


    @staticmethod
    async def get_flow_history_by_record_id(record_group_id: str, record_id: str) -> list[FlowHistory]:
        """根据record_group_id获取flow信息"""
        record_group_collection = MongoDB.get_collection("record_group")
        flow_context_collection = MongoDB.get_collection("flow_context")
        try:
            record_group = await record_group_collection.aggregate([
                {"$match": {"_id": record_group_id}},
                {"$unwind": "$records"},
                {"$match": {"records.record_id": record_id}},
            ])
            records = await record_group.to_list(length=1)
            if not records:
                return []

            flow_context_list = []
            for flow_context_id in records[0]["records"]["flow"]:
                flow_context = await flow_context_collection.find_one({"_id": flow_context_id})
                if flow_context:
                    flow_context = FlowHistory.model_validate(flow_context)
                    flow_context_list.append(flow_context)

            return flow_context_list

        except Exception as e:
            LOGGER.error(f"[TaskManager] Get flow history by record_id failed: {e}")
            return []


    @staticmethod
    async def get_flow_history_by_task_id(task_id: str) -> dict[str, FlowHistory]:
        """根据task_id获取flow信息"""
        flow_context_collection = MongoDB.get_collection("flow_context")

        flow_context = {}
        try:
            async for history in flow_context_collection.find({"task_id": task_id}):
                history_obj = FlowHistory.model_validate(history)
                flow_context[history_obj.step_id] = history_obj

            return flow_context
        except Exception as e:
            LOGGER.error(f"[TaskManager] Get flow history by task_id failed: {e}")
            return {}


    @staticmethod
    async def create_flows(flow_context: list[FlowHistory]) -> None:
        """保存flow信息到flow_context"""
        flow_context_collection = MongoDB.get_collection("flow_context")
        try:
            flow_context_str = [flow.model_dump(by_alias=True) for flow in flow_context]
            await flow_context_collection.insert_many(flow_context_str)
        except Exception as e:
            LOGGER.error(f"[TaskManager] Create flow failed: {e}")


    @staticmethod
    async def delete_tasks_by_conversation_id(conversation_id: str) -> None:
        """通过ConversationID删除Task信息"""
        task_collection = MongoDB.get_collection("task")
        flow_context_collection = MongoDB.get_collection("flow_context")
        try:
            async with MongoDB.get_session() as session, await session.start_transaction():
                task_ids = [task["_id"] async for task in task_collection.find({"conversation_id": conversation_id}, {"_id": 1}, session=session)]
                await task_collection.delete_many({"conversation_id": conversation_id}, session=session)
                await flow_context_collection.delete_many({"task_id": {"$in": task_ids}}, session=session)
                await session.commit_transaction()
        except Exception as e:
            LOGGER.error(f"[TaskManager] Delete tasks by conversation_id failed: {e}")
