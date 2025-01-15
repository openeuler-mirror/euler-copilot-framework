# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
import os
import unittest
from unittest.mock import patch, MagicMock, create_autospec
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from apps.models.mysql import MysqlDB


class TestMysqlDB(unittest.TestCase):

    @patch('apps.models.mysql_db.create_engine')
    @patch('apps.models.mysql_db.get_logger')
    @patch('apps.models.mysql_db.CryptoHub.query_plaintext_by_config_name')
    @patch('os.getenv')
    def test_init_success(self, mock_getenv, mock_query_plaintext, mock_get_logger, mock_create_engine):
        # 模拟环境变量和密码查询
        def mock_getenv_side_effect(x):
            return {
                "MYSQL_USER": "test_user",
                "MYSQL_HOST": "test_host",
                "MYSQL_PORT": "3306",
                "MYSQL_DATABASE": "test_db"
            }.get(x)

        mock_getenv.side_effect = mock_getenv_side_effect
        mock_query_plaintext.return_value = "test_password"

        # 模拟create_engine方法引发异常
        mock_create_engine.side_effect = Exception("Error creating engine")

        # 创建一个 Mock 对象来模拟 logger.error 方法
        mock_logger_error = MagicMock()

        # 设置 mock_get_logger.return_value 为我们创建的 Mock 对象
        mock_get_logger.return_value.error = mock_logger_error

        # 执行测试
        mysql_db = MysqlDB()

        # 断言 logger.error 被正确调用
        mock_logger_error.assert_called_once_with("Error creating a session: Error creating engine")

    @patch('apps.models.mysql_db.MysqlDB.get_session')
    def test_get_session_success(self, mock_get_session):
        mock_session = MagicMock(spec=Session)
        mock_get_session.return_value = mock_session

        mysql_db = MysqlDB()
        session = mysql_db.get_session()

        mock_get_session.assert_called_once()
        self.assertEqual(session, mock_session)

    # Add tests for other scenarios for get_session method...

    @patch('apps.models.mysql_db.MysqlDB.get_session')
    def test_get_session_exception(self, mock_get_session):
        mock_get_session.return_value = None

        mysql_db = MysqlDB()
        session = mysql_db.get_session()

        mock_get_session.assert_called_once()
        self.assertIsNone(session)

    # Add tests for other scenarios for get_session method...

    @patch('apps.models.mysql_db.get_logger')
    def test_close_success(self, mock_get_logger):
        mock_engine = MagicMock(spec=Engine)
        mysql_db = MysqlDB()
        mysql_db.engine = mock_engine

        mysql_db.close()

        mock_engine.dispose.assert_called_once()

    # Add tests for other scenarios for close method...


if __name__ == '__main__':
    unittest.main()
