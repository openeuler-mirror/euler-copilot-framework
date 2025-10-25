# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户 Manager"""

import logging
import secrets
from datetime import UTC, datetime

from sqlalchemy import func, select

from apps.common.postgres import postgres
from apps.models import User
from apps.schemas.request_data import UserUpdateRequest

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
    async def get_usernames_by_ids(user_ids: set[str]) -> dict[str, str]:
        """
        根据用户ID集合批量获取用户名

        :param user_ids: 用户ID集合
        :return: 用户ID到用户名的映射字典
        """
        if not user_ids:
            return {}

        async with postgres.session() as session:
            users = (await session.scalars(
                select(User).where(User.id.in_(user_ids)),
            )).all()
            return {user.id: user.userName for user in users}

    @staticmethod
    async def get_user_ids_by_username_keyword(keyword: str) -> list[str]:
        """
        根据用户名关键字查询所有匹配的用户ID

        :param keyword: 用户名关键字
        :return: 匹配的用户ID列表
        """
        if not keyword:
            return []

        async with postgres.session() as session:
            users = (await session.scalars(
                select(User).where(User.userName.like(f"%{keyword}%")),
            )).all()
            return [user.id for user in users]


    @staticmethod
    async def update_user_info(user_id: str, data: UserUpdateRequest) -> None:
        """
        更新已有用户的属性信息

        :param user_id: 用户ID
        :param data: 更新数据
        :raises ValueError: 如果用户不存在
        """
        async with postgres.session() as session:
            user = (
                await session.scalars(select(User).where(User.id == user_id))
            ).one_or_none()
            if not user:
                error_msg = f"[UserManager] User {user_id} not found"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # 更新指定字段
            update_dict = data.model_dump(exclude_unset=True, exclude_none=True, by_alias=True)
            for key, value in update_dict.items():
                if hasattr(user, key):
                    setattr(user, key, value)

            await session.commit()

    @staticmethod
    async def create_or_update_on_login(user_id: str, user_name: str | None = None) -> None:
        """
        在登录时创建新用户或更新已有用户的 lastLogin 时间

        :param user_id: 用户ID
        :param user_name: 用户名（仅在创建新用户时使用）
        """
        async with postgres.session() as session:
            user = (
                await session.scalars(select(User).where(User.id == user_id))
            ).one_or_none()

            if not user:
                # 创建新用户
                user = User(
                    id=user_id,
                    userName=user_name or f"用户-{secrets.token_hex(8)}",
                    isActive=True,
                    isWhitelisted=False,
                    credit=0,
                )
                session.add(user)
            else:
                # 更新已有用户的登录时间
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
