"""获取和保存Task信息到数据库

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import logging
from typing import Optional

from apps.entities.collection import RecordGroup
from apps.entities.task import FlowStepHistory, TaskData
from apps.manager.record import RecordManager
from apps.models.mongo import MongoDB

logger = logging.getLogger("ray")


class TaskManager:
    """从数据库中获取任务信息"""

    @staticmethod
    async def get_task_by_conversation_id(conversation_id: str) -> Optional[TaskData]:
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
        task_collection = MongoDB.get_collection("task")
        task = await task_collection.find_one({"_id": task_id})
        if not task:
            # 任务不存在，新建Task
            logger.error("[TaskManager] 任务 %s 不存在", task_id)
            return None

        task = TaskData.model_validate(task)
        if task.ended:
            # Task已结束，新建Task
            return None

        return task

    @staticmethod
    async def get_task_by_group_id(group_id: str, conversation_id: str) -> Optional[TaskData]:
        """获取组ID的最后一条问答组关联的任务"""
        task_collection = MongoDB.get_collection("task")
        record_group_collection = MongoDB.get_collection("record_group")
        try:
            record_group = await record_group_collection.find_one({"conversation_id": conversation_id, "_id": group_id})
            if not record_group:
                return None
            record_group_obj = RecordGroup.model_validate(record_group)
            task = await task_collection.find_one({"_id": record_group_obj.task_id})
            return TaskData.model_validate(task)
        except Exception:
            logger.exception("[TaskManager] 获取组ID的最后一条问答组关联的任务失败")
            return None

    @staticmethod
    async def get_flow_history_by_record_id(record_group_id: str, record_id: str) -> list[FlowStepHistory]:
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
                    flow_context = FlowStepHistory.model_validate(flow_context)
                    flow_context_list.append(flow_context)

            return flow_context_list

        except Exception:
            logger.exception("[TaskManager] 获取record_id的flow信息失败")
            return []


    @staticmethod
    async def get_flow_history_by_task_id(task_id: str) -> dict[str, FlowStepHistory]:
        """根据task_id获取flow信息"""
        flow_context_collection = MongoDB.get_collection("flow_context")

        flow_context = {}
        try:
            async for history in flow_context_collection.find({"task_id": task_id}):
                history_obj = FlowStepHistory.model_validate(history)
                flow_context[history_obj.step_id] = history_obj

            return flow_context
        except Exception:
            logger.exception("[TaskManager] 获取task_id的flow信息失败")
            return {}


    @staticmethod
    async def create_flows(flow_context: list[FlowStepHistory]) -> None:
        """保存flow信息到flow_context"""
        flow_context_collection = MongoDB.get_collection("flow_context")
        try:
            flow_context_str = [flow.model_dump(by_alias=True) for flow in flow_context]
            await flow_context_collection.insert_many(flow_context_str)
        except Exception:
            logger.exception("[TaskManager] 创建flow信息失败")


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
        except Exception:
            logger.exception("[TaskManager] 通过ConversationID删除Task信息失败")
