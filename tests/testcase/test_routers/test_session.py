# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from fastapi.testclient import TestClient
from fastapi import Request, FastAPI
from starlette.requests import HTTPConnection

from apps.routers.conversation import router
from apps.models.mysql import User
from apps.dependency import verify_csrf_token, get_current_user


def mock_csrf_token(request: HTTPConnection):
    return


def mock_get_user(request: Request):
    return User(user_sub="1", organization="openEuler")


class TestSessionsRouter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[verify_csrf_token] = mock_csrf_token
        app.dependency_overrides[get_current_user] = mock_get_user
        cls.client = TestClient(app)

    @patch('apps.routers.session.UserQaRecordManager.get_user_qa_record_by_user_sub')
    @patch('apps.routers.session.QaManager.query_total_encrypted_qa_pair_by_sessionid')
    @patch('apps.routers.session.UserQaRecordManager.update_user_qa_record_title_create_time_by_session_id')
    def test_get_session_list_success(self, mock_update_user_qa_record_title_create_time_by_session_id,
                                      mock_query_total_encrypted_qa_pair_by_sessionid,
                                      mock_get_user_qa_record_by_user_sub):
        mock_query_total_encrypted_qa_pair_by_sessionid.return_value = [1, 2, 3]
        mock_update_user_qa_record_title_create_time_by_session_id.return_value = None

        converse = MagicMock()
        converse.user_qa_record_id = "123"
        converse.title = "test"
        converse.created_time = datetime.utcnow()

        mock_get_user_qa_record_by_user_sub.return_value = [converse]
        response = self.client.get("/sessions")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['result']), 1)

    @patch('apps.routers.session.UserQaRecordManager.update_user_qa_record_title_create_time_by_session_id')
    @patch('apps.routers.session.QaManager.query_total_encrypted_qa_pair_by_sessionid')
    @patch('apps.routers.session.UserQaRecordManager.get_user_qa_record_by_user_sub')
    def test_add_session_success_empty(self, mock_get_user_qa_record_by_user_sub,
                                       mock_query_total_encrypted_qa_pair_by_sessionid,
                                       mock_update_user_qa_record_title_create_time_by_session_id):
        converse = MagicMock()
        converse.user_qa_record_id = "123"

        mock_get_user_qa_record_by_user_sub.return_value = [converse]
        mock_update_user_qa_record_title_create_time_by_session_id.return_value = None
        mock_query_total_encrypted_qa_pair_by_sessionid.return_value = []

        response = self.client.post("/sessions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "code": 200,
            "message": "success",
            "result": {
                "session_id": "123",
            }
        })

    @patch('apps.routers.session.UserQaRecordManager.get_user_qa_record_by_user_sub')
    @patch('apps.routers.session.UserQaRecordManager.add_user_qa_record_by_user_sub')
    def test_add_session_success_nonempty(self, mock_add_user_qa_record_by_user_sub,
                                          mock_get_user_qa_record_by_user_sub):
        mock_get_user_qa_record_by_user_sub.return_value = []
        mock_add_user_qa_record_by_user_sub.return_value = "123"

        response = self.client.post("/sessions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "code": 200,
            "message": "success",
            "result": {
                "session_id": "123",
            }
        })

    @patch('apps.routers.session.UserQaRecordManager.get_user_qa_record_by_session_id')
    @patch('apps.routers.session.UserQaRecordManager.update_user_qa_record_by_session_id')
    def test_update_session_success(self, mock_update_user_qa_record_by_session_id,
                                    mock_get_user_qa_record_by_session_id):
        cur_user_qa_record = MagicMock()
        cur_user_qa_record.user_sub = "1"
        mock_get_user_qa_record_by_session_id.return_value = cur_user_qa_record

        converse = MagicMock()
        converse.user_qa_record_id = "123"
        converse.title = "test"
        converse.created_time = datetime.utcnow()
        mock_update_user_qa_record_by_session_id.return_value = converse

        response = self.client.put("/sessions", json={"title": "new title"},
                                   params={"session_id": "123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "code": 200,
            "message": "success",
            "result": {
                "session": {
                    "session_id": "123",
                    "title": "test",
                    "created_time": converse.created_time.strftime("%Y-%m-%dT%H:%M:%S.%f"),
                }
            }
        })

    @patch('apps.routers.session.UserQaRecordManager.get_user_qa_record_by_session_id')
    def test_update_session_empty(self, mock_get_user_qa_record_by_session_id):
        mock_get_user_qa_record_by_session_id.return_value = None

        response = self.client.put("/sessions", json={"title": "new title"},
                                   params={"session_id": "123"})
        self.assertEqual(response.status_code, 204)

    @patch('apps.routers.session.AuditLogManager.add_audit_log')
    @patch('apps.routers.session.UserQaRecordManager.delete_user_qa_record_by_session_id')
    @patch('apps.routers.session.QaManager.delete_encrypted_qa_pair_by_sessionid')
    @patch('apps.routers.session.UserQaRecordManager.get_user_qa_record_by_session_id')
    def test_delete_session_success(self, mock_get_user_qa_record_by_session_id,
                                    mock_delete_encrypted_qa_pair_by_sessionid,
                                    mock_delete_user_qa_record_by_session_id,
                                    mock_add_audit_log):
        cur_user_qa_record = MagicMock()
        cur_user_qa_record.user_sub = "1"
        mock_get_user_qa_record_by_session_id.return_value = cur_user_qa_record

        mock_delete_encrypted_qa_pair_by_sessionid.return_value = None
        mock_delete_user_qa_record_by_session_id.return_value = None
        mock_add_audit_log.return_value = None

        response = self.client.post("/sessions/delete", json={"session_id_list": ["123"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "code": 200,
            "message": "success",
            "result": {
                "session_id_list": ["123"]
            }
        })

    @patch('apps.routers.session.UserQaRecordManager.get_user_qa_record_by_session_id')
    def test_delete_session_empty(self, mock_get_user_qa_record_by_session_id):
        mock_get_user_qa_record_by_session_id.return_value = None

        response = self.client.post("/sessions/delete", json={"session_id_list": ["aaa", "bbb"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "code": 200,
            "message": "success",
            "result": {
                "session_id_list": []
            }
        })

    @patch('apps.routers.session.RedisConnectionPool.get_redis_connection')
    def test_stop_generation(self, mock_redis_connection):
        mock_redis_connection.return_value = MagicMock()
        response = self.client.post("/sessions/stop_generation")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "code": 200,
            "message": "stop generation success",
            "result": {}
        })


if __name__ == '__main__':
    unittest.main()
