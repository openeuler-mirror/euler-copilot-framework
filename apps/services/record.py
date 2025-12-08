# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问答对Manager"""

import json
import logging
import uuid
from typing import Literal

from sqlalchemy import and_, select

from apps.common.postgres import postgres
from apps.common.security import Security
from apps.models import Conversation
from apps.models import Record as PgRecord
from apps.models import RecordMetadata as PgRecordMetadata
from apps.schemas.record import RecordContent, RecordData, RecordMetadata

logger = logging.getLogger(__name__)


class RecordManager:
    """问答对相关操作"""

    @staticmethod
    async def get_conversation_and_record(
        user_id: str,
        conversation_id: uuid.UUID,
        record_id: uuid.UUID | None = None,
    ) -> tuple[bool, PgRecord | None]:
        """
        验证对话是否存在且获取已存在的记录

        :param user_id: 用户ID
        :param conversation_id: 会话ID
        :param record_id: 记录ID（可选）
        :return: (对话是否存在, 已存在的记录或None)
        """
        async with postgres.session() as session:
            # 验证对话是否存在
            conv = (await session.scalars(
                select(Conversation).where(
                    and_(
                        Conversation.id == conversation_id,
                        Conversation.userId == user_id,
                    ),
                ),
            )).one_or_none()

            if not conv:
                return False, None

            # 如果提供了record_id，则查找已存在的记录
            if record_id:
                existing_record = (await session.scalars(
                    select(PgRecord).where(
                        and_(
                            PgRecord.id == record_id,
                            PgRecord.conversationId == conversation_id,
                        ),
                    ),
                )).one_or_none()
                return True, existing_record

            return True, None

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
    async def insert_record_data(
        user_id: str,
        conversation_id: uuid.UUID,
        record: PgRecord,
        metadata: PgRecordMetadata,
    ) -> uuid.UUID | None:
        """Record和RecordMetadata插入PostgreSQL"""
        # 验证对话存在并检查是否有同ID的记录
        conv_exists, existing_record = await RecordManager.get_conversation_and_record(
            user_id,
            conversation_id,
            record.id,
        )

        if not conv_exists:
            logger.error("[RecordManager] 对话不存在: %s", conversation_id)
            return None

        async with postgres.session() as session:
            if existing_record:
                logger.warning("[RecordManager] 记录已存在,删除旧记录后重新保存: %s", record.id)
                # 删除已存在的记录及其元数据
                existing_metadata = (await session.scalars(
                    select(PgRecordMetadata).where(PgRecordMetadata.recordId == record.id),
                )).one_or_none()
                if existing_metadata:
                    await session.delete(existing_metadata)
                await session.delete(existing_record)
                await session.flush()

            session.add(record)
            session.add(metadata)
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
        # 验证对话是否存在
        conv_exists, _ = await RecordManager.get_conversation_and_record(
            user_id,
            conversation_id,
        )

        if not conv_exists:
            logger.error("[RecordManager] 对话不存在: %s", conversation_id)
            return []

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
                decrypted_content = Security.decrypt(pg_record.content, pg_record.key)
                record_content = RecordContent.model_validate(json.loads(decrypted_content))

                record = RecordData(
                    id=pg_record.id,
                    conversationId=pg_record.conversationId,
                    taskId=pg_record.taskId,
                    content=record_content,
                    createdAt=pg_record.createdAt.timestamp(),
                    metadata=RecordMetadata(),
                )
                records.append(record)
            return records
