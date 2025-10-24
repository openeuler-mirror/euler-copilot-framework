# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户 Manager"""

import logging
import secrets
from datetime import UTC, datetime

from sqlalchemy import func, select

from apps.common.postgres import postgres
from apps.models import User

from .conversation import ConversationManager

logger = logging.getLogger(__name__)


class UserManager:
    """用户相关操作"""

    @staticmethod
    async def list_user(n: int = 10, page: int = 1) -> tuple[list[User], int]:
        """
        获取所有用户

        :param n: 每页数量
        :param page: 页码
        :return: 所有用户列表
        """
        async with postgres.session() as session:
            count = await session.scalar(select(func.count(User.id)))
            users = (await session.scalars(select(User).offset((page - 1) * n).limit(n))).all()
            return list(users), count or 0


    @staticmethod
    async def get_user(user_id: str) -> User | None:
        """
        根据用户ID获取用户信息

        :param user_id: 用户ID
        :return: 用户信息
        """
        async with postgres.session() as session:
            return (
                await session.scalars(select(User).where(User.id == user_id))
            ).one_or_none()


    @staticmethod
    async def update_user(user_id: str, data: dict) -> None:
        """
        根据用户sub更新用户信息

        :param user_id: 用户ID
        :param data: 更新数据
        """
        async with postgres.session() as session:
            user = (
                await session.scalars(select(User).where(User.id == user_id))
            ).one_or_none()
            if not user:
                user = User(
                    userName=data.get("userName", f"用户-{secrets.token_hex(8)}"),
                    isActive=True,
                    isWhitelisted=False,
                    credit=0,
                )
                await session.merge(user)
                await session.commit()
                return

            # 更新指定字段
            for key, value in data.items():
                if hasattr(user, key) and value is not None:
                    setattr(user, key, value)

            user.lastLogin = datetime.now(tz=UTC)
            await session.commit()

    @staticmethod
    async def delete_user(user_id: str) -> None:
        """
        根据用户sub删除用户信息

        :param user_id: 用户ID
        """
        async with postgres.session() as session:
            user = (
                await session.scalars(select(User).where(User.id == user_id))
            ).one_or_none()
            if not user:
                return

            await session.delete(user)
            await session.commit()

            await ConversationManager.delete_conversation_by_user(user_id)
