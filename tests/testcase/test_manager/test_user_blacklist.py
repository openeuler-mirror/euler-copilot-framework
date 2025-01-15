from unittest import TestCase, TestLoader
from unittest.mock import patch
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import pytz

from apps.manager.blacklist import UserBlacklistManager
from apps.models.mysql import (
    Base,
    User
)


class TestBlacklistManager(TestCase):
    engine = None

    @classmethod
    def setUpClass(cls):
        TestLoader.sortTestMethodsUsing = None

        cls.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(cls.engine)

        # Test data
        with Session(cls.engine) as session:
            session.add_all([
                User(
                    user_sub="10000",
                    organization='openEuler',
                    revision_number='1.0.0',
                    credit=0,
                    is_whitelisted=False,
                    login_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai')),
                    created_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
                ),
                User(
                    user_sub="10001",
                    organization='openEuler',
                    revision_number='1.0.0',
                    credit=10,
                    is_whitelisted=False,
                    login_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai')),
                    created_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
                ),
                User(
                    user_sub="10002",
                    organization='openEuler',
                    revision_number='1.0.0',
                    credit=0,
                    is_whitelisted=True,
                    login_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai')),
                    created_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
                )
            ])
            session.commit()

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_00_get_blacklisted_users_empty(self, mock_mysql_db):
        # Empty engine
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session
            result = UserBlacklistManager.get_blacklisted_users(10, 0)
            self.assertEqual(len(result), 0)

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_01_get_blacklisted_users_success(self, mock_mysql_db):
        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session
            result = UserBlacklistManager.get_blacklisted_users(10, 0)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['user_sub'], "10000")

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_02_check_blacklisted_users_success(self, mock_mysql_db):
        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session
            result = UserBlacklistManager.check_blacklisted_users(10000)
            self.assertTrue(result)

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_03_check_blacklisted_users_failed(self, mock_mysql_db):
        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session
            result = UserBlacklistManager.check_blacklisted_users(10001)
            self.assertFalse(result)
            result = UserBlacklistManager.check_blacklisted_users(10002)
            self.assertFalse(result)

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_04_change_blacklisted_users_success(self, mock_mysql_db):
        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session
            # 信用分正常
            result = UserBlacklistManager.change_blacklisted_users("10001", 20)
            self.assertTrue(result)
            # 信用分超限
            result = UserBlacklistManager.change_blacklisted_users("10000", 200)
            self.assertTrue(result)
            result = UserBlacklistManager.check_blacklisted_users("10000")
            self.assertFalse(result)
            result = UserBlacklistManager.change_blacklisted_users("10000", -200)
            self.assertTrue(result)
            result = UserBlacklistManager.check_blacklisted_users("10000")
            self.assertTrue(result)

    @patch('apps.manager.blacklist_manager.MysqlDB')
    def test_05_change_blacklisted_users_failed(self, mock_mysql_db):
        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session
            # 用户不存在
            result = UserBlacklistManager.change_blacklisted_users("10003", 100)
            self.assertTrue(result)
            # 用户在白名单内
            result = UserBlacklistManager.change_blacklisted_users("10002", -100)
            self.assertFalse(result)
            result = UserBlacklistManager.check_blacklisted_users("10002")
            self.assertFalse(result)
