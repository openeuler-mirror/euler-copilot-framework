# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import logging
import unittest
from unittest.mock import patch, MagicMock
from apps.manager.record import RecordManager, Record, MysqlDB


class TestQaManager(unittest.TestCase):

    @patch('apps.manager.qa_manager.MysqlDB')
    def test_insert_encrypted_qa_pair_success(self, mock_mysql_db):
        user_qa_record_id = "test_user_qa_record_id"
        qa_record_id = "test_qa_record_id"
        user_sub = "test_user_sub"
        question = "test_question"
        answer = "test_answer"
        mock_session = MagicMock()
        mock_mysql_db.return_value.get_session.return_value.__enter__.return_value = mock_session

        RecordManager.insert_encrypted_data(user_qa_record_id, qa_record_id, user_sub, question, answer)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch('apps.manager.qa_manager.MysqlDB')
    @patch('apps.manager.qa_manager.Security')
    @patch('apps.manager.qa_manager.get_logger')
    def test_insert_encrypted_qa_pair_encryption_failure(self, mock_get_logger, mock_security, mock_mysql_db):
        # Mock encrypt method to raise an exception
        mock_encrypt = MagicMock(side_effect=Exception("Encryption error"))
        mock_security.encrypt = mock_encrypt

        # Mock logger
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        user_qa_record_id = "test_user_qa_record_id"
        qa_record_id = "test_qa_record_id"
        user_sub = "test_user_sub"
        question = "test_question"
        answer = "test_answer"

        mock_session = MagicMock()
        mock_mysql_db.return_value.get_session.return_value.__enter__.return_value = mock_session

        # Call the method under test
        RecordManager.insert_encrypted_data(user_qa_record_id, qa_record_id, user_sub, question, answer)

        # Assert that logger methods were not called
        mock_logger.assert_not_called()

        # Assert that database operations were not called
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    @patch('apps.manager.qa_manager.MysqlDB')
    def test_query_encrypted_qa_pair_by_sessionid_success(self, mock_mysql_db):
        user_qa_record_id = "test_user_qa_record_id"
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            Record(user_qa_record_id=user_qa_record_id)
        ]
        mock_mysql_db.return_value.get_session.return_value.__enter__.return_value = mock_session

        results = RecordManager.query_encrypted_data_by_conversation_id(user_qa_record_id)

        self.assertEqual(len(results), 1)


if __name__ == '__main__':
    unittest.main()
