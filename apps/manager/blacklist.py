"""黑名单相关操作

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import logging

from apps.common.security import Security
from apps.entities.collection import (
    Blacklist,
    Record,
    RecordContent,
    User,
)
from apps.models.mongo import MongoDB

logger = logging.getLogger(__name__)


class QuestionBlacklistManager:
    """问题黑名单相关操作"""

    @staticmethod
    async def check_blacklisted_questions(input_question: str) -> bool:
        """给定问题，查找问题是否在黑名单里"""
        try:
            blacklist_collection = MongoDB.get_collection("blacklist")
            result = await blacklist_collection.find_one({"question": {"$regex": f"/{input_question}/"}, "is_audited": True}, {"_id": 1})
            if result:
                # 用户输入的问题中包含黑名单问题的一部分，故拉黑
                logger.info("[QuestionBlacklistManager] 问题在黑名单中")
                return False
            return True
        except Exception:
            # 访问数据库异常
            logger.exception("[QuestionBlacklistManager] 检查问题黑名单失败")
            return False

    @staticmethod
    async def change_blacklisted_questions(blacklist_id: str, question: str, answer: str, *, is_deletion: bool = False) -> bool:
        """删除或修改已在黑名单里的问题

        is_deletion标识是否为删除操作
        """
        try:
            blacklist_collection = MongoDB.get_collection("blacklist")

            if is_deletion:
                await blacklist_collection.find_one_and_delete({"_id": blacklist_id})
                logger.info("[QuestionBlacklistManager] 问题从黑名单中删除")
                return True

            # 修改
            await blacklist_collection.find_one_and_update({"_id": blacklist_id}, {"$set": {"question": question, "answer": answer}})
            logger.info("[QuestionBlacklistManager] 问题在黑名单中修改")
            return True

        except Exception:
            # 数据库操作异常
            logger.exception("[QuestionBlacklistManager] 修改问题黑名单失败")
            # 放弃执行后续操作
            return False

    @staticmethod
    async def get_blacklisted_questions(limit: int, offset: int, *, is_audited: bool) -> list[Blacklist]:
        """分页式获取目前所有的问题（待审核或已拉黑）黑名单"""
        try:
            blacklist_collection = MongoDB.get_collection("blacklist")
            return [Blacklist.model_validate(item) async for item in blacklist_collection.find({"is_audited": is_audited}).skip(offset).limit(limit)]
        except Exception:
            logger.exception("[QuestionBlacklistManager] 查询问题黑名单失败")
            # 异常
            return []


class UserBlacklistManager:
    """用户黑名单相关操作"""

    @staticmethod
    async def get_blacklisted_users(limit: int, offset: int) -> list[str]:
        """获取当前所有黑名单用户"""
        try:
            user_collection = MongoDB.get_collection("user")
            return [
                user["_id"] async for user in user_collection.find({"credit": {"$lte": 0}}, {"_id": 1}).sort({"_id": 1}).skip(offset).limit(limit)
            ]
        except Exception:
            logger.exception("[UserBlacklistManager] 查询用户黑名单失败")
            return []

    @staticmethod
    async def check_blacklisted_users(user_sub: str) -> bool:
        """检测某用户是否已被拉黑"""
        try:
            user_collection = MongoDB.get_collection("user")
            result = await user_collection.find_one({"user_sub": user_sub, "credit": {"$lte": 0}, "is_whitelisted": False}, {"_id": 1})
            if result is not None:
                logger.info("[UserBlacklistManager] 用户在黑名单中")
                return True
            return False
        except Exception:
            logger.exception("[UserBlacklistManager] 检查用户黑名单失败")
            return False

    @staticmethod
    async def change_blacklisted_users(user_sub: str, credit_diff: int, credit_limit: int = 100) -> bool:
        """修改用户的信用分"""
        try:
            # 获取用户当前信用分
            user_collection = MongoDB.get_collection("user")
            result = await user_collection.find_one({"user_sub": user_sub}, {"_id": 0, "credit": 1})
            # 用户不存在
            if result is None:
                logger.info("[UserBlacklistManager] 用户不存在")
                return False

            result = User.model_validate(result)
            # 用户已被加白，什么都不做
            if result.is_whitelisted:
                return False

            if result.credit > 0 and credit_diff > 0:
                logger.info("[UserBlacklistManager] 用户已解禁")
                return True
            if result.credit <= 0 and credit_diff < 0:
                logger.info("[UserBlacklistManager] 用户已封禁")
                return True

            # 给当前用户的信用分加上偏移量
            new_credit = result.credit + credit_diff
            # 不得超过积分上限
            if new_credit > credit_limit:
                new_credit = credit_limit
            # 不得小于0
            elif new_credit < 0:
                new_credit = 0

            # 更新用户信用分
            await user_collection.update_one({"user_sub": user_sub}, {"$set": {"credit": new_credit}})
            return True
        except Exception:
            # 数据库错误
            logger.exception("[UserBlacklistManager] 修改用户黑名单失败")
            return False


class AbuseManager:
    """用户举报相关操作"""

    @staticmethod
    async def change_abuse_report(user_sub: str, record_id: str, reason_type: list[str], reason: str) -> bool:
        """存储用户举报详情"""
        try:
            # 判断record_id是否合法
            record_group_collection = MongoDB.get_collection("record_group")
            record = await record_group_collection.aggregate([
                {"$match": {"user_sub": user_sub}},
                {"$unwind": "$records"},
                {"$match": {"records._id": record_id}},
                {"$limit": 1},
            ])

            record = await record.to_list(length=1)
            if not record:
                logger.info("[AbuseManager] 举报记录不合法")
                return False

            # 获得Record明文内容
            record = Record.model_validate(record[0]["records"])
            record_data = Security.decrypt(record.data, record.key)
            record_data = RecordContent.model_validate_json(record_data)

            # 检查该条目类似内容是否已被举报过
            blacklist_collection = MongoDB.get_collection("question_blacklist")
            query = await blacklist_collection.find_one({"_id": record_id})
            if query is not None:
                logger.info("[AbuseManager] 问题已被举报过")
                return True

            # 增加新条目
            new_blacklist = Blacklist(
                _id=record_id,
                is_audited=False,
                question=record_data.question,
                answer=record_data.answer,
                reason_type=reason_type,
                reason=reason,
            )

            await blacklist_collection.insert_one(new_blacklist.model_dump(by_alias=True))
            return True
        except Exception:
            logger.exception("[AbuseManager] 修改用户举报失败")
            return False

    @staticmethod
    async def audit_abuse_report(question_id: str, *, is_deletion: bool = False) -> bool:
        """对某一特定的待审问题进行操作，包括批准审核与删除未审问题"""
        try:
            blacklist_collection = MongoDB.get_collection("blacklist")
            if is_deletion:
                await blacklist_collection.delete_one({"_id": question_id, "is_audited": False})
                return True
            await blacklist_collection.update_one(
                {"_id": question_id, "is_audited": False},
                {"$set": {"is_audited": True}},
            )
            return True
        except Exception:
            logger.exception("[AbuseManager] 审核用户举报失败")
            return False
