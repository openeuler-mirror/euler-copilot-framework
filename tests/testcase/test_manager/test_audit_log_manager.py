# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.manager.audit_log import AuditLogManager, AuditLogData
from apps.models.mysql import Base, AuditLog


class TestAuditLogManager(unittest.TestCase):
    engine = None

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(cls.engine)

    @patch('apps.manager.audit_log_manager.MysqlDB')
    def test_add_audit_log_success(self, mock_mysql_db):
        user_sub = "1"
        data = AuditLogData(method_type="GET", source_name="test_source", ip="127.0.0.1", result="Success", reason="")

        with Session(self.engine) as session:
            mock_mysql_db.return_value.get_session.return_value = session

            AuditLogManager.add_audit_log(user_sub, data)

            result = session.query(AuditLog).all()
            self.assertEqual(len(result), 1)

    @patch('apps.manager.audit_log_manager.MysqlDB')
    @patch('apps.manager.audit_log_manager.get_logger')
    def test_add_audit_log_failed(self, mock_get_logger, mock_mysql_db):
        user_sub = "test_user_sub"
        data = AuditLogData(method_type="GET", source_name="test_source", ip="127.0.0.1", result="Success", reason="")

        # 模拟日志记录器的 info 方法
        with patch.object(AuditLogManager.logger, 'info') as mock_info:
            mock_session = MagicMock()
            mock_session.add.side_effect = Exception("Database error")
            mock_mysql_db.return_value.get_session.return_value.__enter__.return_value = mock_session

            # 调用被测试的函数
            AuditLogManager.add_audit_log(user_sub, data)

            # 断言 info 方法被正确调用
            mock_info.assert_called_once_with(
                "Add audit log failed due to error: Database error")


if __name__ == '__main__':
    unittest.main()
