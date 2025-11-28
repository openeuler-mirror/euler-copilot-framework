# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""会话 Manager"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from apps.common.postgres import postgres
from apps.constants import SESSION_TTL
from apps.models import Session, SessionType

logger = logging.getLogger(__name__)


class SessionManager:
    """浏览器Session管理"""

    @staticmethod
    async def create_session(user_id: str, ip: str) -> str:
        """创建浏览器Session"""
        if not ip:
            err = "用户IP错误！"
            raise ValueError(err)

        if not user_id:
            err = "用户ID错误！"
            raise ValueError(err)

        data = Session(
            userId=user_id,
            ip=ip,
            validUntil=datetime.now(UTC) + timedelta(minutes=SESSION_TTL),
            sessionType=SessionType.CODE,
        )

        async with postgres.session() as session:
            await session.merge(data)
            await session.commit()

        return data.id


    @staticmethod
    async def delete_session(session_id: str) -> None:
        """删除浏览器Session"""
        if not session_id:
            return
        async with postgres.session() as session:
            session_data = (await session.scalars(select(Session).where(Session.id == session_id))).one_or_none()
            if session_data:
                await session.delete(session_data)
            await session.commit()


    @staticmethod
    async def get_user(session_id: str) -> str | None:
        """从Session中获取用户ID"""
        async with postgres.session() as session:
            user_id = (
                await session.scalars(select(Session.userId).where(Session.id == session_id))
            ).one_or_none()
            if not user_id:
                return None

        return user_id


    @staticmethod
    async def get_session_by_user(user_id: str) -> str | None:
        """根据用户ID获取Session"""
        async with postgres.session() as session:
            data = await session.scalars(select(Session.id).where(Session.userId == user_id))
            return data.one_or_none()
