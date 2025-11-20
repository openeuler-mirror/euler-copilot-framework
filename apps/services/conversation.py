# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""对话 Manager"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, select

from apps.common.postgres import postgres
from apps.models import App, Conversation, UserAppUsage

from .task import TaskManager

logger = logging.getLogger(__name__)


class ConversationManager:
    """对话管理器"""

    @staticmethod
    async def get_conversation_by_user(user_id: str) -> list[Conversation]:
        """根据用户ID获取对话列表，按时间由近到远排序"""
        async with postgres.session() as session:
            result = (await session.scalars(
                select(Conversation).where(
                    and_(
                        Conversation.userId == user_id,
                        Conversation.isTemporary == False,  # noqa: E712
                    ),
                ).order_by(
                    Conversation.createdAt.desc(),
                ),
            )).all()
            return list(result)


    @staticmethod
    async def get_conversation_by_conversation_id(user_id: str, conversation_id: uuid.UUID) -> Conversation | None:
        """通过ConversationID查询对话信息"""
        async with postgres.session() as session:
            return (await session.scalars(
                select(Conversation).where(
                    and_(
                        Conversation.id == conversation_id,
                        Conversation.userId == user_id,
                    ),
                ),
            )).one_or_none()


    @staticmethod
    async def verify_conversation_access(user_id: str, conversation_id: uuid.UUID) -> bool:
        """验证对话是否属于用户"""
        async with postgres.session() as session:
            result = (await session.scalars(
                func.count(Conversation.id).where(
                    and_(
                        Conversation.id == conversation_id,
                        Conversation.userId == user_id,
                    ),
                ),
            )).one()
            return bool(result)


    @staticmethod
    async def add_conversation_by_user(
        title: str, user_id: str, app_id: uuid.UUID | None = None,
        *,
        debug: bool = False,
    ) -> Conversation | None:
        """通过用户ID新建对话"""
        # 使用PostgreSQL实现新建对话
        try:
            async with postgres.session() as session:
                # 如果提供了app_id，验证其是否存在
                if app_id:
                    app_exists = (await session.scalars(
                        select(App.id).where(App.id == app_id),
                    )).one_or_none()
                    if not app_exists:
                        logger.error("[ConversationManager] App ID %s 不存在", app_id)
                        return None

                conv = Conversation(
                    userId=user_id,
                    appId=app_id,
                    isTemporary=debug,
                    title=title,
                )
                session.add(conv)
                await session.commit()
                await session.refresh(conv)

                if app_id and not debug:
                    app_obj = (await session.scalars(
                        select(UserAppUsage).where(
                            and_(
                                UserAppUsage.userId == user_id,
                                UserAppUsage.appId == app_id,
                            ),
                        ),
                    )).one_or_none()
                    if app_obj:
                        app_obj.usageCount += 1
                        app_obj.lastUsed = datetime.now(tz=UTC)
                        await session.merge(app_obj)
                        await session.commit()
                    else:
                        await session.merge(UserAppUsage(
                            userId=user_id,
                            appId=app_id,
                            usageCount=1,
                            lastUsed=datetime.now(tz=UTC),
                        ))
                        await session.commit()
                return conv
        except Exception:
            logger.exception("[ConversationManager] 新建对话失败")
            return None


    @staticmethod
    async def update_conversation_by_conversation_id(
        user_id: str, conversation_id: uuid.UUID, data: dict[str, Any],
    ) -> bool:
        """通过ConversationID更新对话信息"""
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
                return False
            for key, value in data.items():
                setattr(conv, key, value)
            await session.merge(conv)
            await session.commit()
            return True


    @staticmethod
    async def delete_conversation_by_conversation_id(user_id: str, conversation_id: uuid.UUID) -> None:
        """通过ConversationID删除对话"""
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
                return

            await session.delete(conv)
            await session.commit()

        await TaskManager.delete_tasks_by_conversation_id(conversation_id)


    @staticmethod
    async def delete_conversation_by_user(user_id: str) -> None:
        """通过用户ID删除对话"""
        async with postgres.session() as session:
            convs = list((await session.scalars(
                select(Conversation).where(Conversation.userId == user_id),
            )).all())
            for conv in convs:
                await session.delete(conv)
                await TaskManager.delete_tasks_by_conversation_id(conv.id)
            await session.commit()


    @staticmethod
    async def verify_conversation_id(user_id: str, conversation_id: uuid.UUID) -> bool:
        """验证对话ID是否属于用户"""
        async with postgres.session() as session:
            result = (await session.scalars(
                func.count(Conversation.id).where(
                    and_(
                        Conversation.id == conversation_id,
                        Conversation.userId == user_id,
                    ),
                ),
            )).one()
            return bool(result)
