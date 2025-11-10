# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""黑名单相关操作"""

import logging
import uuid

from sqlalchemy import and_, select

from apps.common.postgres import postgres
from apps.common.security import Security
from apps.models import Blacklist, Record, User
from apps.schemas.blacklist import BlacklistedUser
from apps.schemas.record import RecordContent

logger = logging.getLogger(__name__)


class QuestionBlacklistManager:
    """问题黑名单相关操作"""

    @staticmethod
    async def check_blacklisted_questions(input_question: str) -> bool:
        """给定问题，查找问题是否在黑名单里"""
        async with postgres.session() as session:
            # 查找是否有审核通过的黑名单问题包含输入的问题
            blacklist_item = (await session.scalars(select(Blacklist).where(
                and_(
                    Blacklist.question.ilike(f"%{input_question}%"),
                    Blacklist.isAudited == True,  # noqa: E712
                ),
            ).limit(1))).one_or_none()

            if blacklist_item:
                # 用户输入的问题中包含黑名单问题的一部分，故拉黑
                logger.info("[QuestionBlacklistManager] 问题在黑名单中")
                return False
        return True

    @staticmethod
    async def change_blacklisted_questions(
        blacklist_id: str, question: str, answer: str, *, is_deletion: bool = False,
    ) -> bool:
        """
        删除或修改已在黑名单里的问题

        is_deletion标识是否为删除操作
        """
        async with postgres.session() as session:
            # 根据ID查找黑名单记录
            blacklist_item = await session.get(Blacklist, int(blacklist_id))

            if not blacklist_item:
                logger.info("[QuestionBlacklistManager] 黑名单记录不存在")
                return False

            if is_deletion:
                await session.delete(blacklist_item)
                logger.info("[QuestionBlacklistManager] 问题从黑名单中删除")
            else:
                # 修改
                blacklist_item.question = question
                blacklist_item.answer = answer
                logger.info("[QuestionBlacklistManager] 问题在黑名单中修改")

            await session.commit()
            return True

    @staticmethod
    async def get_blacklisted_questions(limit: int, offset: int, *, is_audited: bool) -> list[Blacklist]:
        """分页式获取目前所有的问题（待审核或已拉黑）黑名单"""
        async with postgres.session() as session:
            return list((await session.scalars(select(Blacklist).where(
                Blacklist.isAudited == is_audited,
            ).offset(offset).limit(limit))).all())


class UserBlacklistManager:
    """用户黑名单相关操作"""

    @staticmethod
    async def get_blacklisted_users(limit: int, offset: int) -> list[BlacklistedUser]:
        """获取当前所有黑名单用户"""
        async with postgres.session() as session:
            users = (await session.scalars(select(User).where(
                User.credit <= 0,
            ).order_by(User.userName).offset(offset).limit(limit))).all()
            return [BlacklistedUser(user_id=user.id, user_name=user.userName) for user in users]

    @staticmethod
    async def check_blacklisted_users(user_id: str) -> bool:
        """检测某用户是否已被拉黑"""
        async with postgres.session() as session:
            conditions = [
                User.credit <= 0,
                User.isWhitelisted == False,  # noqa: E712
                User.id == user_id,
            ]

            user = (await session.scalars(select(User).where(
                and_(*conditions),
            ).limit(1))).one_or_none()

            if user:
                logger.info("[UserBlacklistManager] 用户在黑名单中")
                return True
            return False

    @staticmethod
    async def change_blacklisted_users(user_id: str, credit_diff: int, credit_limit: int = 100) -> bool:
        """修改用户的信用分"""
        async with postgres.session() as session:
            # 获取用户当前信用分
            user = (await session.scalars(select(User).where(User.id == user_id))).one_or_none()

            # 用户不存在
            if user is None:
                logger.info("[UserBlacklistManager] 用户不存在")
                return False

            # 用户已被加白，什么都不做
            if user.isWhitelisted:
                return False

            if user.credit > 0 and credit_diff > 0:
                logger.info("[UserBlacklistManager] 用户已解禁")
                return True
            if user.credit <= 0 and credit_diff < 0:
                logger.info("[UserBlacklistManager] 用户已封禁")
                return True

            # 给当前用户的信用分加上偏移量
            new_credit = user.credit + credit_diff
            # 不得超过积分上限
            if new_credit > credit_limit:
                new_credit = credit_limit
            # 不得小于0
            elif new_credit < 0:
                new_credit = 0

            # 更新用户信用分
            user.credit = new_credit
            await session.commit()
            return True


class AbuseManager:
    """用户举报相关操作"""

    @staticmethod
    async def change_abuse_report(user_id: str, record_id: uuid.UUID, reason_type: str, reason: str) -> bool:
        """存储用户举报详情"""
        async with postgres.session() as session:
            # Verify user exists
            user = (await session.scalars(select(User).where(User.id == user_id))).one_or_none()
            if not user:
                logger.info("[AbuseManager] 用户不存在")
                return False

            record = (await session.scalars(select(Record).where(
                and_(
                    Record.userId == user_id,
                    Record.id == record_id,
                ),
            ))).one_or_none()

            if not record:
                logger.info("[AbuseManager] 举报记录不合法")
                return False

            # 获得Record明文内容
            record_data = Security.decrypt(record.content, record.key)
            record_content = RecordContent.model_validate_json(record_data)

            # 检查该条目类似内容是否已被举报过
            existing_blacklist = (await session.scalars(select(Blacklist).where(
                Blacklist.recordId == record_id,
            ).limit(1))).one_or_none()

            if existing_blacklist is not None:
                logger.info("[AbuseManager] 问题已被举报过")
                return True

            # 增加新条目
            new_blacklist = Blacklist(
                recordId=record_id,
                question=record_content.question,
                answer=record_content.answer,
                isAudited=False,
                reasonType=reason_type,
                reason=reason,
            )

            session.add(new_blacklist)
            await session.commit()
            return True

    @staticmethod
    async def audit_abuse_report(record_id: uuid.UUID, *, is_deletion: bool = False) -> bool:
        """对某一特定的待审问题进行操作，包括批准审核与删除未审问题"""
        async with postgres.session() as session:
            blacklist_item = (await session.scalars(select(Blacklist).where(
                and_(
                    Blacklist.recordId == record_id,
                    Blacklist.isAudited == False,  # noqa: E712
                ),
            ))).one_or_none()

            if not blacklist_item:
                logger.info("[AbuseManager] 待审核问题不存在")
                return False

            if is_deletion:
                await session.delete(blacklist_item)
            else:
                blacklist_item.isAudited = True

            await session.commit()
            return True
