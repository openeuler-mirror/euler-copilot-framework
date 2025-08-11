# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""获取和保存Task信息到数据库"""

import logging
import uuid
from typing import Any

from apps.common.mongo import MongoDB
from apps.schemas.record import RecordGroup
from apps.schemas.request_data import RequestData
from apps.schemas.task import (
    Task,
    TaskIds,
    TaskRuntime,
    TaskTokens,
    FlowStepHistory
)
from apps.services.record import RecordManager

logger = logging.getLogger(__name__)


class TaskManager:
    """从数据库中获取任务信息"""

    @staticmethod
    async def get_task_by_conversation_id(conversation_id: str) -> Task | None:
        """获取对话ID的最后一条问答组关联的任务"""
        # 查询对话ID的最后一条问答组
        last_group = await RecordManager.query_record_group_by_conversation_id(conversation_id, 1)
        if not last_group or len(last_group) == 0:
            logger.error("[TaskManager] 没有找到对话 %s 的问答组", conversation_id)
            # 空对话或无效对话，新建Task
            return None

        last_group = last_group[0]
        task_id = last_group.task_id

        # 查询最后一条问答组关联的任务
        task_collection = MongoDB().get_collection("task")
        task = await task_collection.find_one({"_id": task_id})
        if not task:
            # 任务不存在，新建Task
            logger.error("[TaskManager] 任务 %s 不存在", task_id)
            return None

        return Task.model_validate(task)

    @staticmethod
    async def get_task_by_group_id(group_id: str, conversation_id: str) -> Task | None:
        """获取组ID的最后一条问答组关联的任务"""
        task_collection = MongoDB().get_collection("task")
        record_group_collection = MongoDB().get_collection("record_group")
        record_group = await record_group_collection.find_one({"conversation_id": conversation_id, "_id": group_id})
        if not record_group:
            return None
        record_group_obj = RecordGroup.model_validate(record_group)
        task = await task_collection.find_one({"_id": record_group_obj.task_id})
        return Task.model_validate(task)

    @staticmethod
    async def get_task_by_task_id(task_id: str) -> Task | None:
        """根据task_id获取任务"""
        task_collection = MongoDB().get_collection("task")
        task = await task_collection.find_one({"_id": task_id})
        if not task:
            return None
        return Task.model_validate(task)

    @staticmethod
    async def get_context_by_record_id(record_group_id: str, record_id: str) -> list[FlowStepHistory]:
        """根据record_group_id获取flow信息"""
        record_group_collection = MongoDB().get_collection("record_group")
        flow_context_collection = MongoDB().get_collection("flow_context")
        try:
            record_group = await record_group_collection.aggregate([
                {"$match": {"_id": record_group_id}},
                {"$unwind": "$records"},
                {"$match": {"records.id": record_id}},
            ])
            records = await record_group.to_list(length=1)
            if not records:
                return []

            flow_context_list = []
            for flow_context_id in records[0]["records"]["flow"]["history_ids"]:
                flow_context = await flow_context_collection.find_one({"_id": flow_context_id})
                if flow_context:
                    flow_context_list.append(FlowStepHistory.model_validate(flow_context))
        except Exception:
            logger.exception("[TaskManager] 获取record_id的flow信息失败")
            return []
        else:
            return flow_context_list

    @staticmethod
    async def get_context_by_task_id(task_id: str, length: int | None = None) -> list[FlowStepHistory]:
        """根据task_id获取flow信息"""
        flow_context_collection = MongoDB().get_collection("flow_context")

        flow_context = []
        try:
            if length is None:
                async for context in flow_context_collection.find({"task_id": task_id}):
                    flow_context.append(FlowStepHistory.model_validate(context))
            else:
                async for context in flow_context_collection.find({"task_id": task_id}).limit(length):
                    flow_context.append(FlowStepHistory.model_validate(context))
        except Exception:
            logger.exception("[TaskManager] 获取task_id的flow信息失败")
            return []
        else:
            return flow_context

    @staticmethod
    async def init_new_task(
        user_sub: str,
        session_id: str | None = None,
        post_body: RequestData | None = None,
    ) -> Task:
        """获取任务块"""
        return Task(
            _id=str(uuid.uuid4()),
            ids=TaskIds(
                user_sub=user_sub if user_sub else "",
                session_id=session_id if session_id else "",
                conversation_id=post_body.conversation_id,
                group_id=post_body.group_id if post_body.group_id else "",
            ),
            question=post_body.question if post_body else "",
            group_id=post_body.group_id if post_body else "",
            tokens=TaskTokens(),
            runtime=TaskRuntime(),
        )

    @staticmethod
    async def save_flow_context(task_id: str, flow_context: list[FlowStepHistory]) -> None:
        """保存flow信息到flow_context"""
        flow_context_collection = MongoDB().get_collection("flow_context")
        try:
            # 删除旧的flow_context
            await flow_context_collection.delete_many({"task_id": task_id})
            if not flow_context:
                return
            await flow_context_collection.insert_many(
                [history.model_dump(exclude_none=True, by_alias=True) for history in flow_context],
                ordered=False,
            )
        except Exception:
            logger.exception("[TaskManager] 保存flow执行记录失败")

    @staticmethod
    async def delete_task_by_task_id(task_id: str) -> None:
        """通过task_id删除Task信息"""
        mongo = MongoDB()
        task_collection = mongo.get_collection("task")

        task = await task_collection.find_one({"_id": task_id}, {"_id": 1})
        if task:
            await task_collection.delete_one({"_id": task_id})

    @staticmethod
    async def delete_tasks_by_conversation_id(conversation_id: str) -> list[str]:
        """通过ConversationID删除Task信息"""
        mongo = MongoDB()
        task_collection = mongo.get_collection("task")
        task_ids = []
        try:
            async for task in task_collection.find(
                {"conversation_id": conversation_id},
                {"_id": 1},
            ):
                task_ids.append(task["_id"])
            if task_ids:
                await task_collection.delete_many({"conversation_id": conversation_id})
            return task_ids
        except Exception:
            logger.exception("[TaskManager] 删除ConversationID的Task信息失败")
            return []

    @staticmethod
    async def delete_tasks_and_flow_context_by_conversation_id(conversation_id: str) -> None:
        """通过ConversationID删除Task信息"""
        mongo = MongoDB()
        task_collection = mongo.get_collection("task")
        flow_context_collection = mongo.get_collection("flow_context")

        async with mongo.get_session() as session, await session.start_transaction():
            task_ids = [
                task["_id"] async for task in task_collection.find(
                    {"conversation_id": conversation_id},
                    {"_id": 1},
                    session=session,
                )
            ]
            await task_collection.delete_many({"conversation_id": conversation_id}, session=session)
            await flow_context_collection.delete_many({"task_id": {"$in": task_ids}}, session=session)

    @classmethod
    async def save_task(cls, task_id: str, task: Task) -> None:
        """保存任务块"""
        task_collection = MongoDB().get_collection("task")

        # 更新已有的Task记录
        await task_collection.update_one(
            {"_id": task_id},
            {"$set": task.model_dump(by_alias=True, exclude_none=True)},
            upsert=True,
        )
