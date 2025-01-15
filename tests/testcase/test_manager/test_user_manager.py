# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from apps.manager.user import UserManager, User
from apps.models.mysql import User as UserModel, MysqlDB


class TestUserManager(unittest.TestCase):

    @patch('apps.models.mysql_db.MysqlDB')
    @patch('apps.logger.get_logger')
    def test_add_userinfo_failure(self, mock_get_logger, mock_mysql_db):
        # 创建模拟的 logger 对象
        mock_logger = MagicMock()

        # 将模拟的 logger 对象分配给 UserManager.logger
        UserManager.logger = mock_logger

        userinfo = User(user_sub="test_user_sub", organization="test_org", revision_number="123")

        # 创建模拟的数据库会话对象
        mock_session = MagicMock()

        # 模拟 get_session 方法并返回模拟的数据库会话对象
        mock_get_session = MagicMock(return_value=mock_session)
        mock_mysql_db.return_value.get_session = mock_get_session

        # 修改 mock_session，使其支持上下文管理器协议
        mock_session.__enter__.return_value = mock_session
        mock_session.__exit__.return_value = False

        # 调用被测试方法
        UserManager.add_userinfo(userinfo)

        # 断言模拟的 logger 对象的 info 方法被调用一次，并且调用时传入了预期的日志信息
        mock_logger.info.assert_called_once_with("Add userinfo failed due to error: __enter__")

    @patch.object(MysqlDB, 'get_session')
    def test_get_userinfo_by_user_sub_success(self, mock_get_session):
        user_sub = "test_user_sub"
        revision_number = 1  # 设置一个合适的修订号

        # 创建模拟对象，确保与被测试的方法中使用的查询一致
        mock_query = MagicMock()
        mock_user = UserModel(user_sub=user_sub, revision_number=revision_number)
        mock_query.filter.return_value.first.side_effect = [mock_user, None]
        mock_session = MagicMock(query=mock_query)
        mock_get_session.return_value.__enter__.return_value = mock_session

        # 调用被测试的方法
        result = UserManager.get_userinfo_by_user_sub(user_sub)

        # 断言结果不为 None
        self.assertIsNotNone(result)

    @patch('apps.models.mysql_db.MysqlDB')
    @patch('apps.manager.user_manager.UserManager.get_userinfo_by_user_sub')
    def test_update_userinfo_by_user_sub_success(self, mock_get_userinfo, mock_mysql_db):
        # 创建测试数据
        userinfo = User(user_sub="test_user_sub", organization="test_org", revision_number="123")

        # 模拟 get_userinfo_by_user_sub 方法返回一个已存在的用户信息对象
        mock_get_userinfo.return_value = userinfo

        # 模拟 MysqlDB 类的实例和方法
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None  # 模拟用户信息不存在的情况
        mock_session.query.return_value = mock_query
        mock_mysql_db_instance = mock_mysql_db.return_value
        mock_mysql_db_instance.get_session.return_value = mock_session

        # 调用被测方法
        updated_userinfo = UserManager.update_userinfo_by_user_sub(userinfo, refresh_revision=True)

        # 断言返回的用户信息的 revision_number 是否与原始用户信息一致
        self.assertEqual(updated_userinfo.revision_number, userinfo.revision_number)


if __name__ == '__main__':
    unittest.main()
