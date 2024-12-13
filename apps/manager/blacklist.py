# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from __future__ import annotations

import json
import logging

from sqlalchemy import select

from apps.common.security import Security
from apps.models.mysql import (
    MysqlDB,
    Record,
    QuestionBlacklist,
    User,
    Conversation,
)


logger = logging.getLogger('gunicorn.error')


class QuestionBlacklistManager:
    def __init__(self):
        raise NotImplementedError("QuestionBlacklistManager无法被实例化")

    # 给定问题，查找问题是否在黑名单里
    @staticmethod
    def check_blacklisted_questions(input_question: str) -> bool | None:
        try:
            # 搜索问题
            with MysqlDB().get_session() as session:
                result = session.scalars(
                    select(QuestionBlacklist).filter_by(is_audited=True)
                    .order_by(QuestionBlacklist.id)
                )

                # 问题表为空，则下面的代码不会执行
                for item in result:
                    if item.question in input_question:
                        # 用户输入的问题中包含黑名单问题的一部分，故拉黑
                        logger.info("Question in blacklist.")
                        return False

                return True
        except Exception as e:
            # 访问数据库异常
            logger.info(f"Check question blacklist failed: {e}")
            return None

    # 删除或修改已在黑名单里的问题，is_deletion标识是否为删除操作
    @staticmethod
    def change_blacklisted_questions(question: str, answer: str, is_deletion: bool = False) -> bool:
        try:
            with MysqlDB().get_session() as session:
                # 搜索问题，精确匹配
                result = session.scalars(
                    select(QuestionBlacklist).filter_by(is_audited=True).filter_by(question=question).limit(1)
                ).first()

                if result is None:
                    if not is_deletion:
                        # 没有查到任何结果，进行添加问题
                        logger.info("Question not found in blacklist.")
                        session.add(QuestionBlacklist(question=question, answer=answer, is_audited=True,
                                                      reason_description="手动添加"))
                    else:
                        logger.info("Question does not exist.")
                else:
                    # search_question就是搜到的结果，进行答案更改
                    if not is_deletion:
                        # 修改
                        logger.info("Modify question in blacklist.")

                        result.question = question
                        result.answer = answer
                    else:
                        # 删除
                        logger.info("Delete question in blacklist.")
                        session.delete(result)

                session.commit()
                return True
        except Exception as e:
            # 数据库操作异常
            logger.info(f"Change question blacklist failed: {e}")
            # 放弃执行后续操作
            return False

    # 分页式获取目前所有的问题（待审核或已拉黑）黑名单
    @staticmethod
    def get_blacklisted_questions(limit: int, offset: int, is_audited: bool) -> list | None:
        try:
            with MysqlDB().get_session() as session:
                query = session.scalars(
                    # limit：取多少条；offset：跳过前多少条；
                    select(QuestionBlacklist).filter_by(is_audited=is_audited).
                    order_by(QuestionBlacklist.id).limit(limit).offset(offset)
                )

                result = []
                # 无条目，则下面的语句不会执行
                for item in query:
                    result.append({
                        "id": item.id,
                        "question": item.question,
                        "answer": item.answer,
                        "reason": item.reason_description,
                        "created_time": item.created_time,
                    })

                return result
        except Exception as e:
            logger.info(f"Query question blacklist failed: {e}")
            # 异常，返回None
            return None


# 用户黑名单相关操作
class UserBlacklistManager:
    def __init__(self):
        raise NotImplementedError("UserBlacklistManager无法被实例化")

    # 获取当前所有黑名单用户
    @staticmethod
    def get_blacklisted_users(limit: int, offset: int) -> list | None:
        try:
            with MysqlDB().get_session() as session:
                result = session.scalars(
                    select(User).order_by(User.user_sub).filter(User.credit <= 0)
                    .filter_by(is_whitelisted=False).limit(limit).offset(offset)
                )

                user = []
                # 无条目，则下面的语句不会执行
                for item in result:
                    user.append({
                        "user_sub": item.user_sub,
                        "organization": item.organization,
                        "credit": item.credit,
                        "login_time": item.login_time
                    })

                return user

        except Exception as e:
            logger.info(f"Query user blacklist failed: {e}")
            return None

    # 检测某用户是否已被拉黑
    @staticmethod
    def check_blacklisted_users(user_sub: str) -> bool | None:
        try:
            with MysqlDB().get_session() as session:
                result = session.scalars(
                    select(User).filter_by(user_sub=user_sub).filter(User.credit <= 0)
                    .filter_by(is_whitelisted=False).limit(1)
                ).first()

                # 有条目，说明被拉黑
                if result is not None:
                    logger.info("User blacklisted.")
                    return True

                return False

        except Exception as e:
            logger.info(f"Check user blacklist failed: {e}")
            return None

    # 修改用户的信用分
    @staticmethod
    def change_blacklisted_users(user_sub: str, credit_diff: int, credit_limit: int = 100) -> bool | None:
        try:
            with MysqlDB().get_session() as session:
                # 查找当前用户信用分
                result = session.scalars(
                    select(User).filter_by(user_sub=user_sub).limit(1)
                ).first()

                # 用户不存在
                if result is None:
                    logger.info("User does not exist.")
                    return False

                # 用户已被加白，什么都不做
                if result.is_whitelisted:
                    return False

                if result.credit > 0 and credit_diff > 0:
                    logger.info("User already unbanned.")
                    return True
                if result.credit <= 0 and credit_diff < 0:
                    logger.info("User already banned.")
                    return True

                # 给当前用户的信用分加上偏移量
                result.credit += credit_diff
                # 不得超过积分上限
                if result.credit > credit_limit:
                    result.credit = credit_limit
                # 不得小于0
                elif result.credit < 0:
                    result.credit = 0

                session.commit()
                return True
        except Exception as e:
            # 数据库错误
            logger.info(f"Change user blacklist failed: {e}")
            return None


# 用户举报相关操作
class AbuseManager:
    def __init__(self):
        raise NotImplementedError("AbuseManager无法被实例化")

    # 存储用户举报详情
    @staticmethod
    def change_abuse_report(user_sub: str, qa_record_id: str, reason: str) -> bool | None:
        try:
            with MysqlDB().get_session() as session:
                # 检查qa_record_id是否在当前user下
                qa_record = session.scalars(
                    select(Record).filter_by(qa_record_id=qa_record_id).limit(1)
                ).first()

                # qa_record_id 不存在
                if qa_record is None:
                    logger.info("QA record invalid.")
                    return False

                user = session.scalars(
                    select(Conversation).filter_by(
                        user_sub=user_sub,
                        user_qa_record_id=qa_record.conversation_id
                    ).limit(1)
                ).first()

                # qa_record_id 不在当前用户下
                if user is None:
                    logger.info("QA record user mismatch.")
                    return False

                # 获得用户的明文输入
                user_question = Security.decrypt(qa_record.encrypted_question,
                                                 json.loads(qa_record.question_encryption_config))
                user_answer = Security.decrypt(qa_record.encrypted_answer,
                                               json.loads(qa_record.answer_encryption_config))

                # 检查该条目是否已被举报
                query = session.scalars(
                    select(QuestionBlacklist).filter_by(question=user_question).order_by(QuestionBlacklist.id).limit(1)
                ).first()
                # 结果为空
                if query is None:
                    # 新增举报信息；具体的举报类型在前端拼接
                    session.add(QuestionBlacklist(
                        question=user_question,
                        answer=user_answer,
                        is_audited=False,
                        reason_description=reason
                    ))
                    session.commit()
                    return True
                else:
                    # 类似问题已待审核/被加入黑名单，什么都不做
                    logger.info("Question has been reported before.")
                    session.commit()
                    return True

        except Exception as e:
            logger.info(f"Change user abuse report failed: {e}")
            return None

    # 对某一特定的待审问题进行操作，包括批准审核与删除未审问题
    @staticmethod
    def audit_abuse_report(question_id: int, is_deletion: int = False) -> bool | None:
        try:
            with MysqlDB().get_session() as session:
                # 从数据库中查找该问题
                question = session.scalars(
                    select(QuestionBlacklist).filter_by(id=question_id).filter_by(is_audited=False).limit(1)
                ).first()

                # 条目不存在
                if question is None:
                    return False

                # 删除
                if is_deletion:
                    session.delete(question)
                else:
                    question.is_audited = True

                session.commit()
                return True
        except Exception as e:
            logger.info(f"Audit user abuse report failed: {e}")
            return None
