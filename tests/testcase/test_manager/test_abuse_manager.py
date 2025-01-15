import json
import unittest
from unittest import TestCase
from unittest.mock import patch
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import pytz

from apps.manager.blacklist import QuestionBlacklistManager, AbuseManager
from apps.models.mysql import (
    Base,
    User,
    Conversation,
    Record,
    QuestionBlacklist,
)
from apps.common.security import Security


class TestBlacklistManager(TestCase):
    engine = None

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(cls.engine)

        # Test pair 1
        enc_quest_1, quest_enc_conf_1 = Security.encrypt("openEuler是基于CentOS的二次分发版本吗？")
        enc_answer_1, answer_enc_conf_1 = Security.encrypt("是的，openEuler是基于CentOS的二次开发版本。")

        # Test pair 2
        enc_quest_2, quest_enc_conf_2 = Security.encrypt("糖醋里脊怎么做？")
        enc_answer_2, answer_enc_conf_2 = Security.encrypt(
            "第一步，先准备适量的猪里脊肉、料酒、淀粉、糖、盐、食用油、番茄酱和水。")

        # Test data
        with Session(cls.engine) as session:
            session.add_all([
                User(
                    user_sub="10001",
                    organization='openEuler',
                    revision_number='1.0.0',
                    credit=10,
                    is_whitelisted=False,
                    login_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai')),
                    created_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
                ),
                Conversation(
                    id=1,
                    user_qa_record_id="22d2e55e8ca1a664db4b87cb565988b4",
                    user_sub="10001",
                    title="openEuler是基于CentOS的二次分发版本吗？",
                    created_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
                ),
                Record(
                    id=1,
                    user_qa_record_id="22d2e55e8ca1a664db4b87cb565988b4",
                    qa_record_id="f56780b7bbb98831916bb7d275a15a9e",
                    encrypted_question=enc_quest_1,
                    question_encryption_config=json.dumps(quest_enc_conf_1),
                    encrypted_answer=enc_answer_1,
                    answer_encryption_config=json.dumps(answer_enc_conf_1),
                    created_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai')),
                    group_id="Test"
                ),
                Record(
                    id=2,
                    user_qa_record_id="22d2e55e8ca1a664db4b87cb565988b4",
                    qa_record_id="db3e60edefae44df3b56f6b1c9ea93c6",
                    encrypted_question=enc_quest_2,
                    question_encryption_config=json.dumps(quest_enc_conf_2),
                    encrypted_answer=enc_answer_2,
                    answer_encryption_config=json.dumps(answer_enc_conf_2),
                    created_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai')),
                    group_id="Test"
                ),
                QuestionBlacklist(
                    id=1,
                    question="糖醋里脊怎么做？",
                    answer="第一步，先准备适量的猪里脊肉、料酒、淀粉、糖、盐、食用油、番茄酱和水。",
                    is_audited=False,
                    reason_description="内容不相关",
                    created_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
                ),
                QuestionBlacklist(
                    id=2,
                    question="“设置”用英语怎么说？",
                    answer="“设置”的英语翻译是“setting”。",
                    is_audited=False,
                    reason_description="内容不相关",
                    created_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
                )
            ])
            session.commit()

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_01_get_abuse_report_empty(self, mock_mysql_db):
        # 用临时空数据库
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session

            result = QuestionBlacklistManager.get_blacklisted_questions(10, 0, False)
            self.assertEqual(len(result), 0)

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_02_get_abuse_report_success(self, mock_mysql_db):
        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session

            result = QuestionBlacklistManager.get_blacklisted_questions(10, 0, False)
            self.assertEqual(len(result), 2)

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_03_audit_abuse_report(self, mock_mysql_db):
        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session

            result = AbuseManager.audit_abuse_report(1)
            self.assertTrue(result)

            result = QuestionBlacklistManager.get_blacklisted_questions(10, 0, True)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["id"], 1)

            result = AbuseManager.audit_abuse_report(2, True)
            self.assertTrue(result)

            result = QuestionBlacklistManager.get_blacklisted_questions(10, 0, True)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["id"], 1)

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_04_change_abuse_report_failed(self, mock_mysql_db):
        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session

            # qa_id不存在
            result = AbuseManager.change_abuse_report(user_sub="10001", qa_record_id="22d2e55e8ca1a664db4b87cb565988b4",
                                                      reason="")
            self.assertFalse(result)
            # user不匹配
            result = AbuseManager.change_abuse_report(user_sub="10002", qa_record_id="f56780b7bbb98831916bb7d275a15a9e",
                                                      reason="")
            self.assertFalse(result)

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_05_change_abuse_report_succeed(self, mock_mysql_db):
        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session

            # 已被举报
            result = AbuseManager.change_abuse_report(user_sub="10001", qa_record_id="db3e60edefae44df3b56f6b1c9ea93c6",
                                                      reason="")
            self.assertTrue(result)

            # 举报成功
            result = AbuseManager.change_abuse_report(user_sub="10001", qa_record_id="f56780b7bbb98831916bb7d275a15a9e",
                                                      reason="")
            self.assertTrue(result)

            result = QuestionBlacklistManager.get_blacklisted_questions(10, 0, False)
            self.assertEqual(len(result), 1)


if __name__ == '__main__':
    unittest.main()
