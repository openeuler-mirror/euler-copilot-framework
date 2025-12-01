# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""获取和保存Task信息到数据库"""

import logging
import uuid

from sqlalchemy import and_, delete, select

from apps.common.postgres import postgres
from apps.models import (
    Conversation,
    ExecutorCheckpoint,
    ExecutorHistory,
    Task,
    TaskRuntime,
)
from apps.schemas.task import TaskData

logger = logging.getLogger(__name__)


class TaskManager:
    """从数据库中获取任务信息"""

    @staticmethod
    async def get_task_by_conversation_id(conversation_id: uuid.UUID, user_id: str) -> Task:
        """获取对话ID的最后一个任务"""
        async with postgres.session() as session:
            # 检查user_id是否匹配Conversation
            conversation = (await session.scalars(
                select(Conversation.id).where(
                    and_(
                        Conversation.id == conversation_id,
                        Conversation.userId == user_id,
                    ),
                ),
            )).one_or_none()
            if not conversation:
                err = f"对话不存在或无权访问: {conversation_id}"
                raise RuntimeError(err)

            task = (await session.scalars(
                select(Task).where(Task.conversationId == conversation_id).order_by(Task.updatedAt.desc()).limit(1),
            )).one_or_none()
            if not task:
                # 任务不存在，新建Task
                new_task = Task(
                    conversationId=conversation_id,
                    userId=user_id,
                )
                logger.info("[TaskManager] 创建新任务对象 (未保存)")
                return new_task
            logger.info("[TaskManager] 找到已存在的任务 %s", task.id)
            return task


    @staticmethod
    async def get_task_data_by_task_id(task_id: uuid.UUID, context_length: int | None = None) -> TaskData | None:
        """根据task_id获取任务"""
        async with postgres.session() as session:
            task_data = (await session.scalars(
                select(Task).where(Task.id == task_id),
            )).one_or_none()
            if not task_data:
                logger.error("[TaskManager] 任务不存在 %s", task_id)
                return None

            runtime = (await session.scalars(
                select(TaskRuntime).where(TaskRuntime.taskId == task_id),
            )).one_or_none()
            if not runtime:
                runtime = TaskRuntime(
                    taskId=task_id,
                )

            state = (await session.scalars(
                select(ExecutorCheckpoint).where(ExecutorCheckpoint.taskId == task_id),
            )).one_or_none()

            if context_length == 0:
                context = []
            else:
                context = list((await session.scalars(
                select(ExecutorHistory).where(
                    ExecutorHistory.taskId == task_id,
                ).order_by(ExecutorHistory.updatedAt.desc()).limit(context_length),
            )).all())

            return TaskData(
                metadata=task_data,
                runtime=runtime,
                state=state,
                context=context,
            )


    @staticmethod
    async def delete_task_by_task_id(task_id: uuid.UUID) -> None:
        """通过task_id删除Task信息"""
        async with postgres.session() as session:
            # Delete child tables first to avoid foreign key constraint violations
            await session.execute(
                delete(TaskRuntime).where(TaskRuntime.taskId == task_id),
            )
            await session.execute(
                delete(ExecutorCheckpoint).where(ExecutorCheckpoint.taskId == task_id),
            )
            # Delete parent table last
            await session.execute(
                delete(Task).where(Task.id == task_id),
            )
            await session.commit()


    @staticmethod
    async def delete_tasks_by_conversation_id(conversation_id: uuid.UUID) -> None:
        """通过ConversationID删除Task信息"""
        # 删除Task
        task_ids = []
        async with postgres.session() as session:
            task = list((await session.scalars(
                select(Task).where(Task.conversationId == conversation_id),
            )).all())
            for item in task:
                task_ids.append(item.id)
                await session.delete(item)

            # 删除Task对应的State
            await session.execute(
                delete(ExecutorCheckpoint).where(ExecutorCheckpoint.taskId.in_(task_ids)),
            )
            await session.execute(
                delete(TaskRuntime).where(TaskRuntime.taskId.in_(task_ids)),
            )
            await session.commit()


    @staticmethod
    async def delete_task_context_by_task_id(task_id: uuid.UUID) -> None:
        """通过task_id删除TaskContext信息"""
        async with postgres.session() as session:
            await session.execute(
                delete(ExecutorHistory).where(ExecutorHistory.taskId == task_id),
            )
            await session.commit()


    @staticmethod
    async def delete_task_context_by_conversation_id(conversation_id: uuid.UUID) -> None:
        """通过ConversationID删除TaskContext信息"""
        async with postgres.session() as session:
            task_ids = list((await session.scalars(
                select(Task.id).where(Task.conversationId == conversation_id),
            )).all())
            await session.execute(
                delete(ExecutorHistory).where(ExecutorHistory.taskId.in_(task_ids)),
            )
            await session.commit()


    @staticmethod
    async def save_task(task_data: TaskData) -> None:
        """保存Task、TaskRuntime和ExecutorCheckpoint数据到PostgreSQL"""
        async with postgres.session() as session:
            await session.merge(task_data.metadata)
            await session.merge(task_data.runtime)

            # 保存ExecutorCheckpoint（如果存在）
            if task_data.state:
                await session.merge(task_data.state)

            await session.commit()


    @staticmethod
    async def save_flow_context(context: list[ExecutorHistory]) -> None:
        """保存Flow上下文信息到PostgreSQL"""
        async with postgres.session() as session:
            for ctx in context:
                # 查询是否存在该ExecutorHistory
                existing_history = (await session.scalars(
                    select(ExecutorHistory).where(ExecutorHistory.id == ctx.id),
                )).one_or_none()

                if existing_history:
                    # 更新现有History
                    for key, value in ctx.__dict__.items():
                        if not key.startswith("_"):
                            setattr(existing_history, key, value)
                else:
                    # 插入新History
                    session.add(ctx)

            await session.commit()
