import unittest
from unittest import TestCase
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import pytz

from apps.manager.blacklist import QuestionBlacklistManager
from apps.models.mysql import (
    Base,
    QuestionBlacklist
)


class TestBlacklistManager(TestCase):
    engine = None

    @classmethod
    def setUpClass(cls):

        cls.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(cls.engine)

        with Session(cls.engine) as session:
            # Test data
            session.add_all([
                QuestionBlacklist(
                    id=1,
                    question="openEuler支持哪些处理器架构？",
                    answer="openEuler支持多种处理器架构，包括但不限于鲲鹏处理器。",
                    is_audited=True,
                    reason_description="Test",
                    created_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
                ),
                QuestionBlacklist(
                    id=2,
                    question="你好，很高兴认识你！",
                    answer="你好！很高兴为你提供服务！",
                    is_audited=False,
                    reason_description="Test2",
                    created_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
                )
            ])
            session.commit()

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_00_get_question_blacklist_empty(self, mock_mysql_db):
        # 用临时空数据库
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session
            # 条目为空
            result = QuestionBlacklistManager.get_blacklisted_questions(10, 0, True)
            self.assertEqual(len(result), 0)

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_01_get_question_blacklist_success(self, mock_mysql_db):
        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session
            result = QuestionBlacklistManager.get_blacklisted_questions(10, 0, True)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['id'], 1)

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_02_check_question_blacklist_empty(self, mock_mysql_db):
        # 用临时空数据库
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session
            result = QuestionBlacklistManager.check_blacklisted_questions("测试测试！")
            self.assertTrue(result, True)

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_03_check_question_blacklist_success(self, mock_mysql_db):
        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session
            # 一模一样的问题
            result = QuestionBlacklistManager.check_blacklisted_questions("openEuler支持哪些处理器架构？")
            self.assertFalse(result)
            # 黑名单内问题是用户输入的一部分
            result = QuestionBlacklistManager.check_blacklisted_questions("请告诉我openEuler支持哪些处理器架构？")
            self.assertFalse(result)

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_04_check_question_blacklist_fail(self, mock_mysql_db):
        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session
            # 问题不在黑名单内
            result = QuestionBlacklistManager.check_blacklisted_questions("openEuler是基于Linux的操作系统吗？")
            self.assertTrue(result)
            # 问题未全字匹配
            result = QuestionBlacklistManager.check_blacklisted_questions("openEuler支持哪些架构？")
            self.assertTrue(result)
            # 问题待审核
            result = QuestionBlacklistManager.check_blacklisted_questions("你好，很高兴认识你！")
            self.assertTrue(result)

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_05_change_question_blacklist_add(self, mock_mysql_db):
        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session

            # 增加
            result = QuestionBlacklistManager.change_blacklisted_questions(
                "openEuler是基于CentOS的二次分发版本吗？",
                "不是，openEuler是一个开源的Linux操作系统，它并不是基于CentOS的二次分发版本。",
                False
            )
            self.assertTrue(result)
            result = QuestionBlacklistManager.check_blacklisted_questions(
                "openEuler是基于CentOS的二次分发版本吗？"
            )
            self.assertFalse(result)

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_06_change_question_blacklist_modify(self, mock_mysql_db):
        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session

            # 修改
            result = QuestionBlacklistManager.change_blacklisted_questions(
                "openEuler是基于CentOS的二次分发版本吗？",
                "是的，openEuler是基于CentOS的二次分发版本。",
                False
            )
            assert result == True

            result = QuestionBlacklistManager.check_blacklisted_questions(
                "openEuler是基于CentOS的二次分发版本吗？"
            )
            self.assertFalse(result)

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_07_change_question_blacklist_delete(self, mock_mysql_db):
        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session

            # 删除
            result = QuestionBlacklistManager.change_blacklisted_questions(
                "openEuler是基于CentOS的二次分发版本吗？",
                "是的，openEuler是基于CentOS的二次分发版本。",
                True
            )
            self.assertTrue(result)
            result = QuestionBlacklistManager.check_blacklisted_questions(
                "openEuler是基于CentOS的二次分发版本吗？"
            )
            self.assertTrue(result)

            # 删除不存在的问题
            result = QuestionBlacklistManager.change_blacklisted_questions(
                "什么是iSula？",
                "iSula是一个轻量级容器管理系统。",
                True
            )
            self.assertTrue(result)
            result = QuestionBlacklistManager.check_blacklisted_questions(
                "什么是iSula？"
            )
            self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
