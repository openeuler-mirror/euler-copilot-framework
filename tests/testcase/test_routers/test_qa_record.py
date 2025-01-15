# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from apps.routers.record import router


class TestQaRecordRouter(unittest.TestCase):

    @patch('apps.routers.qa_record.UserQaRecordManager.get_user_qa_record_by_session_id')
    @patch('apps.routers.qa_record.QaManager.query_encrypted_qa_pair_by_sessionid')
    @patch('apps.routers.qa_record.Security.decrypt')
    def test_get_qa_records_success(self, mock_decrypt, mock_query_encrypted_qa_pair_by_sessionid,
                                    mock_get_user_qa_record_by_session_id):
        client = TestClient(router)
        mock_get_user_qa_record_by_session_id.return_value = MagicMock()
        mock_query_encrypted_qa_pair_by_sessionid.return_value = [
            MagicMock(
                user_qa_record_id="123",
                qa_record_id="456",
                encrypted_question="encrypted_question",
                question_encryption_config="question_encryption_config",
                encrypted_answer="encrypted_answer",
                answer_encryption_config="answer_encryption_config",
                created_time="created_time"
            )
        ]
        response = client.get("/qa_record", params={"session_id": "123"}, cookies={"_t": "access_token"})
        assert response.status_code == 200
        assert response.json() == {
            "code": 200,
            "message": "success",
            "result": [
                {
                    "session_id": "123",
                    "record_id": "456",
                    "question": "encrypted_question",
                    "answer": "encrypted_answer",
                    "created_time": "created_time"
                }
            ]
        }

    @patch('apps.routers.qa_record.UserQaRecordManager.get_user_qa_record_by_session_id')
    def test_get_qa_records_session_id_not_found(self, mock_get_user_qa_record_by_session_id):
        client = TestClient(router)
        mock_get_user_qa_record_by_session_id.return_value = None
        response = client.get("/qa_record", params={"session_id": "123"}, cookies={"_t": "access_token"})
        assert response.status_code == 204
        assert response.json() == {
            "code": 204,
            "message": "session_id not found",
            "result": {"session_id": "123"}
        }


if __name__ == '__main__':
    unittest.main()
