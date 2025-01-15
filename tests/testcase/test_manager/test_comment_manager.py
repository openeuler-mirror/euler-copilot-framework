# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from unittest import mock
from unittest.mock import patch, MagicMock
from apps.manager.comment import CommentManager, CommentData, MysqlDB, Comment, get_logger


class TestCommentManager(unittest.TestCase):

    @patch('apps.manager.comment_manager.MysqlDB')
    def test_add_comment_success(self, mock_mysql_db):
        user_sub = "test_user_sub"
        data = CommentData(record_id="qa123", is_like=1, dislike_reason="Reason", reason_link="https://example.com",
                           reason_description="Description")
        mock_session = MagicMock()
        mock_mysql_db.return_value.get_session.return_value.__enter__.return_value = mock_session

        CommentManager.add_comment(user_sub, data)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch('apps.manager.comment_manager.MysqlDB')
    def test_add_comment_exception(self, mock_mysql_db):
        user_sub = "test_user_sub"
        data = CommentData(record_id="qa123", is_like=1, dislike_reason="Reason", reason_link="https://example.com",
                           reason_description="Description")

        # 模拟日志记录器的 info 方法
        with patch.object(CommentManager.logger, 'info') as mock_info:
            mock_session = MagicMock()
            mock_session.add.side_effect = Exception("Database error")
            mock_mysql_db.return_value.get_session.return_value.__enter__.return_value = mock_session

            # 调用被测试的函数
            CommentManager.add_comment(user_sub, data)

            # 断言 info 方法被正确调用
            mock_info.assert_called_once_with(
                "Add comment failed due to error: Database error")

    @patch('apps.manager.comment_manager.MysqlDB')
    def test_delete_comment_by_user_sub_success(self, mock_mysql_db):
        user_sub = "test_user_sub"
        mock_session = MagicMock()
        mock_mysql_db.return_value.get_session.return_value.__enter__.return_value = mock_session

        CommentManager.delete_comment_by_user_sub(user_sub)

        mock_session.query.assert_called_once_with(Comment)
        mock_session.query.return_value.filter.assert_called_once()
        mock_session.query.return_value.filter.return_value.delete.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch('apps.manager.comment_manager.MysqlDB')
    def test_delete_comment_by_user_sub_exception(self, mock_mysql_db):
        user_sub = "test_user_sub"

        # 模拟日志记录器的 info 方法
        with patch.object(CommentManager.logger, 'info') as mock_info:
            mock_session = MagicMock()
            mock_session.query.side_effect = Exception("Database error")
            mock_mysql_db.return_value.get_session.return_value.__enter__.return_value = mock_session

            # 调用被测试的函数
            CommentManager.delete_comment_by_user_sub(user_sub)

            # 断言 info 方法被正确调用
            mock_info.assert_called_once_with(
                "delete comment by user_sub failed due to error: Database error")


if __name__ == '__main__':
    unittest.main()
