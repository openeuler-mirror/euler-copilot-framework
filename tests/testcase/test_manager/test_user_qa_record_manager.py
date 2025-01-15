# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
from apps.models.mysql import MysqlDB, Conversation
from apps.logger import get_logger
from apps.manager.conversation import ConversationManager


class TestUserQaRecordManager(unittest.TestCase):

    def test_get_user_qa_record_by_user_sub(self):
        user_sub = "test_user_sub"
        with patch.object(MysqlDB, 'get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_query = MagicMock()
            mock_all = MagicMock(return_value=["result"])
            mock_query.filter().all = mock_all
            mock_session.query.return_value = mock_query
            mock_get_session.return_value.__enter__.return_value = mock_session
            result = ConversationManager.get_conversation_by_user_sub(user_sub)
            self.assertEqual(result, ["result"])

    def test_get_user_qa_record_by_session_id(self):
        session_id = "test_session_id"
        with patch.object(MysqlDB, 'get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_query = MagicMock()
            mock_first = MagicMock(return_value="result")
            mock_query.filter().first = mock_first
            mock_session.query.return_value = mock_query
            mock_get_session.return_value.__enter__.return_value = mock_session
            result = ConversationManager.get_conversation_by_conversation_id(session_id)
            self.assertEqual(result, "result")

    def test_add_user_qa_record_by_user_sub(self):
        user_sub = "test_user_sub"
        with patch.object(MysqlDB, 'get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_add = MagicMock()
            mock_commit = MagicMock()
            mock_session.add = mock_add
            mock_session.commit = mock_commit
            mock_get_session.return_value.__enter__.return_value = mock_session
            result = ConversationManager.add_conversation_by_user_sub(user_sub)
            self.assertIsInstance(result, str)

    def test_update_user_qa_record_by_session_id(self):
        session_id = "test_session_id"
        title = "test_title"

        # Mock the return value of get_user_qa_record_by_session_id
        mock_user_qa_record = Conversation(id=session_id, title=title)  # Create a mock UserQaRecord instance
        with patch.object(ConversationManager, 'get_user_qa_record_by_session_id', return_value=mock_user_qa_record):
            with patch.object(MysqlDB, 'get_session') as mock_get_session:
                mock_session = MagicMock()
                mock_query = MagicMock()
                mock_update = MagicMock()
                mock_commit = MagicMock()
                mock_session.query.return_value = mock_query
                mock_query.filter().update = mock_update
                mock_session.commit = mock_commit
                mock_get_session.return_value.__enter__.return_value = mock_session

                # Call the method under test
                result = ConversationManager.update_conversation_by_conversation_id(session_id, title)

                # Assert that the result is an instance of UserQaRecord
                self.assertIsInstance(result, Conversation)

    def test_delete_user_qa_record_by_session_id(self):
        session_id = "test_session_id"
        with patch.object(MysqlDB, 'get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_query = MagicMock()
            mock_delete = MagicMock()
            mock_commit = MagicMock()
            mock_session.query.return_value = mock_query
            mock_query.filter().delete = mock_delete
            mock_session.commit = mock_commit
            mock_get_session.return_value.__enter__.return_value = mock_session
            ConversationManager.delete_conversation_by_conversation_id(session_id)
            mock_delete.assert_called_once()

    def test_delete_user_qa_record_by_user_sub(self):
        user_sub = "test_user_sub"
        with patch.object(MysqlDB, 'get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_query = MagicMock()
            mock_delete = MagicMock()
            mock_commit = MagicMock()
            mock_session.query.return_value = mock_query
            mock_query.filter().delete = mock_delete
            mock_session.commit = mock_commit
            mock_get_session.return_value.__enter__.return_value = mock_session
            ConversationManager.delete_conversation_by_user_sub(user_sub)
            mock_delete.assert_called_once()


if __name__ == "__main__":
    unittest.main()
