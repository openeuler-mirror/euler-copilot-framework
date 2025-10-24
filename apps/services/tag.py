# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户标签管理"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from apps.common.postgres import postgres
from apps.models import Tag, UserTag
from apps.schemas.request_data import PostTagData

logger = logging.getLogger(__name__)


class TagManager:
    """用户标签相关操作"""

    @staticmethod
    async def get_all_tag() -> list[Tag]:
        """
        获取所有标签信息

        :return: 标签信息列表
        """
        async with postgres.session() as session:
            tags = (await session.scalars(select(Tag))).all()
            return list(tags)


    @staticmethod
    async def get_tag_by_name(name: str) -> Tag | None:
        """
        根据领域名称获取领域信息

        :param domain_name: 领域名称
        :return: 领域信息
        """
        async with postgres.session() as session:
            return (await session.scalars(select(Tag).where(Tag.name == name).limit(1))).one_or_none()


    @staticmethod
    async def get_tag_by_user(user_id: str) -> list[Tag]:
        """
        根据用户ID获取用户标签信息

        :param user_id: 用户ID
        :return: 用户标签信息
        """
        tags = []
        async with postgres.session() as session:
            user_tags = (await session.scalars(select(UserTag).where(UserTag.userId == user_id))).all()
            for user_tag in user_tags:
                tag = (await session.scalars(select(Tag).where(Tag.id == user_tag.tag))).one_or_none()
                if tag:
                    tags.append(tag)
            return list(tags)


    @staticmethod
    async def add_tag(data: PostTagData) -> None:
        """
        添加领域

        :param domain_data: 领域信息
        """
        async with postgres.session() as session:
            tag = Tag(
                name=data.tag,
                definition=data.description,
            )
            await session.merge(tag)
            await session.commit()


    @staticmethod
    async def update_tag_by_name(data: PostTagData) -> Tag:
        """
        更新领域

        :param domain_data: 领域信息
        :return: 更新后的领域信息
        """
        async with postgres.session() as session:
            tag = (await session.scalars(select(Tag).where(Tag.name == data.tag).limit(1))).one_or_none()
            if not tag:
                error_msg = f"[TagManager] Tag {data.tag} not found"
                logger.error(error_msg)
                raise ValueError(error_msg)

            tag.definition = data.description
            tag.updatedAt = datetime.now(tz=UTC)
            await session.merge(tag)
            await session.commit()
            return tag


    @staticmethod
    async def delete_tag(data: PostTagData) -> None:
        """
        删除领域

        :param domain_data: 领域信息
        """
        async with postgres.session() as session:
            tag = (await session.scalars(select(Tag).where(Tag.name == data.tag).limit(1))).one_or_none()
            if not tag:
                error_msg = f"[TagManager] Tag {data.tag} not found"
                logger.error(error_msg)
                raise ValueError(error_msg)

            await session.delete(tag)
            await session.commit()
