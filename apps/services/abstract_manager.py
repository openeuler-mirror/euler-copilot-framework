# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""摘要 Manager"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from apps.common.postgres import postgres
from apps.models.abstract import Abstract
from apps.models.record import Record
from apps.models.task import Task
from apps.schemas.abstract import AbstractData

logger = logging.getLogger(__name__)


class AbstractManager:
    """摘要管理器（长短记忆数据库服务）"""

    @staticmethod
    async def get_abstracts_by_conversation(
        conversation_id: uuid.UUID,
        start_record_idx: int | None = None,
        end_record_idx: int | None = None,
    ) -> list[AbstractData]:
        """
        获取指定对话下窗口范围内的摘要
        :param conversation_id: 对话ID
        :param start_record_idx: 起始索引（可选）
        :param end_record_idx: 结束索引（可选）
        :return: 窗口范围内的摘要列表（AbstractData格式）
        """  # noqa: D205
        try:
            async with postgres.session() as session:
                # 第一步：先从Task表查询该conversation_id关联的所有recordId
                task_query = select(Task.recordId).where(Task.conversationId == conversation_id)
                record_ids = (await session.scalars(task_query)).all()

                # 无关联recordId则直接返回空列表
                if not record_ids:
                    logger.info("[AbstractManager] 对话%s无关联的recordId，返回空摘要列表", conversation_id)
                    return []

                # 第二步：用recordId列表查询Abstract表（按创建时间降序）
                base_query = select(Abstract).where(Abstract.recordId.in_(record_ids)).order_by(Abstract.createdAt.desc())  # noqa: E501

                # 应用窗口范围（分页）—— 逻辑完全保留
                if start_record_idx is not None and end_record_idx is not None:
                    base_query = base_query.slice(start_record_idx, end_record_idx)
                elif start_record_idx is not None:
                    base_query = base_query.offset(start_record_idx)
                elif end_record_idx is not None:
                    base_query = base_query.limit(end_record_idx)

                # 执行查询并转换为AbstractData（修复from_orm为model_validate）
                abstracts = (await session.scalars(base_query)).all()
                return [AbstractData.model_validate(abs_obj) for abs_obj in abstracts]
        except Exception:
            logger.exception("[AbstractManager] 获取对话摘要失败，conversation_id=%s", conversation_id)
            return []

    @staticmethod
    async def get_abstract(record_id: uuid.UUID) -> AbstractData | None:
        """
        通过record_id查询单个摘要
        :param record_id: 记录ID
        :return: 摘要数据（AbstractData）或None
        """  # noqa: D205
        try:
            async with postgres.session() as session:
                abstract = (await session.scalars(
                    select(Abstract).where(Abstract.recordId == record_id),
                )).one_or_none()
                if abstract:
                    return AbstractData.model_validate(abstract)
                return None
        except Exception:
            logger.exception("[AbstractManager] 查询摘要失败，record_id=%s", record_id)
            return None

    @staticmethod
    async def create_or_update_abstract(
        record_id: uuid.UUID,
        abstract_text: str,
    ) -> bool:
        """
        创建或更新摘要（存在则更新，不存在则创建）
        :param record_id: 记录ID
        :param abstract_text: 摘要内容
        :param keywords: 摘要关键词（预留字段）
        :return: 操作是否成功
        """  # noqa: D205
        try:
            async with postgres.session() as session:
                # 1. 查询是否已存在该record_id的摘要
                existing_abstract = (await session.scalars(
                    select(Abstract).where(Abstract.recordId == record_id),
                )).one_or_none()

                if existing_abstract:
                    # 2. 存在则更新
                    existing_abstract.recordAbstract = abstract_text
                    existing_abstract.updatedAt = datetime.now(tz=UTC)
                    await session.merge(existing_abstract)
                    logger.info("[AbstractManager] 更新摘要成功，record_id=%s", record_id)
                else:
                    # 3. 不存在则创建
                    new_abstract = Abstract(
                        recordId=record_id,
                        recordAbstract=abstract_text,
                        createdAt=datetime.now(tz=UTC),
                        updatedAt=datetime.now(tz=UTC),
                    )
                    session.add(new_abstract)
                    logger.info("[AbstractManager] 创建摘要成功，record_id=%s", record_id)

                await session.commit()
                return True
        except SQLAlchemyError:
            logger.exception("[AbstractManager] 创建/更新摘要失败，record_id=%s", record_id)
            await session.rollback()
            return False
        except Exception:
            logger.exception("[AbstractManager] 创建/更新摘要异常，record_id=%s", record_id)
            return False

    @staticmethod
    async def delete_abstract(record_id: uuid.UUID) -> None:
        """
        删除指定record_id的摘要
        :param record_id: 记录ID
        """  # noqa: D205
        try:
            async with postgres.session() as session:
                abstract = (await session.scalars(
                    select(Abstract).where(Abstract.recordId == record_id)
                )).one_or_none()
                if abstract:
                    await session.delete(abstract)
                    await session.commit()
                    logger.info("[AbstractManager] 删除摘要成功，record_id=%s", record_id)
        except Exception:
            logger.exception("[AbstractManager] 删除摘要失败，record_id=%s", record_id)
            await session.rollback()

    @staticmethod
    async def abstract_exists(record_id: uuid.UUID) -> bool:
        """
        判断指定record_id的摘要是否存在
        :param record_id: 记录ID
        :return: 是否存在
        """  # noqa: D205
        try:
            async with postgres.session() as session:
                count = (await session.scalars(
                    func.count(Abstract.id).where(Abstract.recordId == record_id)
                )).one()
                return bool(count)
        except Exception:
            logger.exception("[AbstractManager] 判断摘要是否存在失败，record_id=%s", record_id)
            return False

    @staticmethod
    async def get_oldest_abstract_by_conversation(conversation_id: uuid.UUID) -> AbstractData | None:
        """
        获取指定对话下最旧的一条摘要（滑动窗口替换旧消息用）
        :param conversation_id: 对话ID
        :return: 最旧摘要或None
        """  # noqa: D205
        # 取最旧的1条：按创建时间升序，取第一条
        oldest_abstracts = await AbstractManager.get_abstracts_by_conversation(
            conversation_id=conversation_id,
            end_record_idx=1,
        )
        # 反转列表（原查询是降序，反转后第一条是最旧）
        oldest_abstracts.reverse()
        return oldest_abstracts[0] if oldest_abstracts else None

    @staticmethod
    async def get_oldest_abstracts_by_conversation(
        conversation_id: uuid.UUID,
        n: int = 1,  # 默认获取1条，兼容原有调用逻辑
    ) -> list[AbstractData]:
        """
        获取指定对话下最旧的n条摘要（滑动窗口替换旧消息用）
        :param conversation_id: 对话ID
        :param n: 要获取的最旧摘要数量，默认1条
        :return: 最旧的n条摘要列表（按创建时间从旧到新排序）
        """  # noqa: D205
        if n <= 0:
            logger.warning("[AbstractManager] 获取最旧摘要时n=%s，返回空列表", n)
            return []

        try:
            async with postgres.session() as session:
                # 第一步：先查该conversation_id关联的recordId
                task_query = select(Record.id).where(Record.conversationId == conversation_id)
                record_ids = (await session.scalars(task_query)).all()
                if not record_ids:
                    return []
                logger.info("[AbstractManager] 获取对话%s关联的recordId成功，recordId数量: %s", conversation_id, len(record_ids))
                # 第二步：按创建时间升序查询（直接拿到最旧的），取前n条
                base_query = (
                    select(Abstract)
                    .where(Abstract.recordId.in_(record_ids))
                    .order_by(Abstract.createdAt.asc())  # 升序=从旧到新
                    .limit(n)  # 直接取最旧的n条
                )

                abstracts = (await session.scalars(base_query)).all()
                # 转换为AbstractData并返回（已按旧→新排序）
                logger.info("[AbstractManager] 获取对话%s最旧的%s条摘要成功，实际获取到%s条", conversation_id, n, len(abstracts))
                return [AbstractData.model_validate(abs_obj) for abs_obj in abstracts]
        except Exception:
            logger.exception("[AbstractManager] 获取对话%s最旧的%s条摘要失败", conversation_id, n)
            return []
