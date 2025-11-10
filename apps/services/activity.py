# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户限流"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from apps.common.postgres import postgres
from apps.constants import MAX_CONCURRENT_TASKS, SLIDE_WINDOW_QUESTION_COUNT, SLIDE_WINDOW_TIME
from apps.exceptions import ActivityError
from apps.models import SessionActivity


class Activity:
    """活动控制：全局并发限制，同时最多有 n 个任务在执行（与用户无关）"""

    @staticmethod
    async def can_active(user_id: str) -> bool:
        """
        判断系统是否达到全局并发上限

        :param user_id: 用户实体ID（兼容现有接口签名）
        :return: 达到并发上限返回 False，否则 True
        """
        time = datetime.now(tz=UTC)

        async with postgres.session() as session:
            # 单用户滑动窗口限流：统计该用户在窗口内的请求数
            count = (await session.scalars(select(func.count(SessionActivity.id)).where(
                SessionActivity.userId == user_id,
                SessionActivity.timestamp >= time - timedelta(seconds=SLIDE_WINDOW_TIME),
                SessionActivity.timestamp <= time,
            ))).one()
            if count >= SLIDE_WINDOW_QUESTION_COUNT:
                return False

            # 全局并发检查：当前活跃任务数量是否达到上限
            current_active = (await session.scalars(select(func.count(SessionActivity.id)))).one()
            return current_active < MAX_CONCURRENT_TASKS

    @staticmethod
    async def set_active(user_id: str) -> None:
        """设置活跃标识：当未超过全局并发上限时登记一个活动任务"""
        time = datetime.now(UTC)
        async with postgres.session() as session:
            # 并发上限校验
            current_active = (await session.scalars(select(func.count(SessionActivity.id)))).one()
            if current_active >= MAX_CONCURRENT_TASKS:
                err = "系统并发已达上限"
                raise ActivityError(err)
            session.add(SessionActivity(userId=user_id, timestamp=time))
            await session.commit()


    @staticmethod
    async def remove_active(user_id: str) -> None:
        """
        释放一个活动任务名额（按发起者标识清除对应记录）

        :param user_id: 用户实体ID
        """
        async with postgres.session() as session:
            await session.execute(
                delete(SessionActivity).where(SessionActivity.userId == user_id),
            )
            await session.commit()
