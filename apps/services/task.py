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

_logger = logging.getLogger(__name__)


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
                _logger.info("[TaskManager] 创建新任务对象 (未保存)")
                return new_task
            _logger.info("[TaskManager] 找到已存在的任务 %s", task.id)
            return task


    @staticmethod
    async def get_task_data_by_task_id(task_id: uuid.UUID, context_length: int | None = None) -> TaskData | None:
        """根据task_id获取任务"""
        async with postgres.session() as session:
            task_data = (await session.scalars(
                select(Task).where(Task.id == task_id),
            )).one_or_none()
            if not task_data:
                _logger.error("[TaskManager] 任务不存在 %s", task_id)
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
                ).order_by(ExecutorHistory.createdAt.asc()).limit(context_length),
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
        """保存Flow上下文信息到PostgreSQL，确保数据库与内存状态一致"""
        if not context:
            return

        async with postgres.session() as session:
            task_id = context[0].taskId
            memory_ids = {ctx.id for ctx in context}

            existing_histories = list((await session.scalars(
                select(ExecutorHistory).where(ExecutorHistory.taskId == task_id),
            )).all())

            existing_map = {history.id: history for history in existing_histories}

            deleted_count = 0
            for existing_id, existing_history in existing_map.items():
                if existing_id not in memory_ids:
                    await session.delete(existing_history)
                    deleted_count += 1
                    _logger.debug(
                        "[TaskManager] 删除已从内存移除的History记录 - task_id: %s, history_id: %s, status: %s",
                        task_id, existing_id, existing_history.stepStatus.value,
                    )

            updated_count = 0
            inserted_count = 0
            for ctx in context:
                existing_history = existing_map.get(ctx.id)

                if existing_history:
                    for key, value in ctx.__dict__.items():
                        if not key.startswith("_"):
                            setattr(existing_history, key, value)
                    updated_count += 1
                else:
                    session.add(ctx)
                    inserted_count += 1

            await session.commit()

            if deleted_count > 0 or inserted_count > 0 or updated_count > 0:
                _logger.info(
                    "[TaskManager] 保存Flow上下文 - task_id: %s, 插入: %d, 更新: %d, 删除: %d",
                    task_id, inserted_count, updated_count, deleted_count,
                )
