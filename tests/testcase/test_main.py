# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import status
from apps.main import query_stream_rag, app


class TestMain(unittest.TestCase):

    def test_natural_language_post_successful(self):
        # Mock request data
        request_data = {
            "question": "test question",
            "session_id": "test_session_id",
            "qa_record_id": "test_qa_record_id"
        }

        # Mock user
        user = {
            "user_sub": "test_user_sub"
        }

        # Mock content generator
        async def mock_query_stream_rag(question, session_id, user_sub, qa_record_id):
            yield "data: mock_content\n\n"

        # Mock Redis connection
        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        # Call the function
        with patch("apps.main.query_stream_rag", side_effect=mock_query_stream_rag):
            with patch("apps.models.redis_db.RedisConnectionPool.get_redis_connection", return_value=mock_redis):
                client = TestClient(app)
                response = client.post("/get_stream_answer", json=request_data, headers=user)

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_natural_language_post_exception(self):
        # Mock request data
        request_data = {
            "question": "test question",
            "session_id": "test_session_id",
            "qa_record_id": "test_qa_record_id"
        }

        # Mock user
        user = {
            "user_sub": "test_user_sub"
        }

        # Mock query_stream_rag to raise exception
        with patch("apps.main.query_stream_rag") as mock_query_stream_rag:
            mock_query_stream_rag.side_effect = Exception("Test exception")

            # Use TestClient to send request
            client = TestClient(app)
            response = client.post("/get_stream_answer", json=request_data, headers=user)

            # Assert the response
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


if __name__ == "__main__":
    unittest.main()
