# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""API Key管理"""

import logging
import uuid

from sqlalchemy import select, update

from apps.common.postgres import postgres
from apps.models import User

logger = logging.getLogger(__name__)


class PersonalTokenManager:
    """Personal Token管理"""

    @staticmethod
    async def get_user_by_personal_token(personal_token: str) -> str | None:
        """
        根据Personal Token获取用户信息

        :param personal_token: Personal Token
        :return: 用户ID
        """
        async with postgres.session() as session:
            try:
                result = (
                    await session.scalars(
                        select(User.userSub).where(User.personalToken == personal_token),
                    )
                ).one_or_none()
            except Exception:
                logger.exception("[PersonalTokenManager] 根据Personal Token获取用户信息失败")
                return None
            else:
                return result


    @staticmethod
    async def update_personal_token(user_sub: str) -> str | None:
        """
        更新Personal Token

        :param user_sub: 用户ID
        :return: 更新后的Personal Token
        """
        personal_token = uuid.uuid4().hex
        personal_token_with_prefix = f"sk-{personal_token}"
        try:
            async with postgres.session() as session:
                await session.execute(
                    update(User).where(User.id == user_sub).values(personal_token=personal_token_with_prefix),
                )
                await session.commit()
        except Exception:
            logger.exception("[PersonalTokenManager] 更新Personal Token失败")
            return None
        return personal_token_with_prefix
