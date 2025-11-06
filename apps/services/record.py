# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问答对Manager"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import and_, select

from apps.common.postgres import postgres
from apps.models import Conversation
from apps.models import Record as PgRecord
from apps.schemas.record import RecordComment, RecordData, RecordMetadata

logger = logging.getLogger(__name__)


class RecordManager:
    """问答对相关操作"""

    @staticmethod
    async def verify_record_in_conversation(record_id: uuid.UUID, user_id: str, conversation_id: uuid.UUID) -> bool:
        """
        校验指定record_id是否属于指定用户和会话（PostgreSQL实现）

        :param record_id: 记录ID
        :param user_id: 用户ID
        :param conversation_id: 会话ID
        :return: 是否存在
        """
        async with postgres.session() as session:
            result = (await session.scalars(
                select(PgRecord).where(
                    and_(
                        PgRecord.id == record_id,
                        PgRecord.userId == user_id,
                        PgRecord.conversationId == conversation_id,
                    ),
            ))).one_or_none()
            return result is not None


    @staticmethod
    async def insert_record_data(user_id: str, conversation_id: uuid.UUID, record: RecordData) -> uuid.UUID | None:
        """Record插入PostgreSQL"""
        async with postgres.session() as session:
            conv = (await session.scalars(
                select(Conversation).where(
                    and_(
                        Conversation.id == conversation_id,
                        Conversation.userId == user_id,
                    ),
                ),
            )).one_or_none()
            if not conv:
                logger.error("[RecordManager] 对话不存在: %s", conversation_id)
                return None

            await session.merge(PgRecord(
                id=record.id,
                conversationId=conversation_id,
                taskId=record.task_id,
                userId=user_id,
                content=record.content,
                key=record.key,
                createdAt=datetime.fromtimestamp(record.created_at, tz=UTC),
            ))
            await session.commit()

        return record.id


    @staticmethod
    async def query_record_by_conversation_id(
        user_id: str,
        conversation_id: uuid.UUID,
        total_pairs: int | None = None,
        order: Literal["desc", "asc"] = "desc",
    ) -> list[RecordData]:
        """查询ConversationID的最后n条问答对"""
        async with postgres.session() as session:
            sql = select(PgRecord).where(
                and_(
                    PgRecord.conversationId == conversation_id,
                    PgRecord.userId == user_id,
                ),
            ).order_by(PgRecord.createdAt.desc() if order == "desc" else PgRecord.createdAt.asc())
            if total_pairs is not None:
                sql = sql.limit(total_pairs)
            result = await session.scalars(sql)
            pg_records = result.all()

            records = []
            for pg_record in pg_records:
                record = RecordData(
                    id=pg_record.id,
                    conversationId=pg_record.conversationId,
                    task_id=pg_record.taskId,
                    user_id=pg_record.userId,
                    content=pg_record.content,
                    key=pg_record.key,
                    createdAt=pg_record.createdAt.timestamp(),
                    metadata=RecordMetadata(),
                    comment=RecordComment(),
                )
                records.append(record)
            return records
