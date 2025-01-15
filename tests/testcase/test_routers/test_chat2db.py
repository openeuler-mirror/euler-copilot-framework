# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from fastapi import Request, FastAPI
from starlette.requests import HTTPConnection

from apps.routers.chat2db import router
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

    @patch("sglang.set_default_backend")
    @patch("apps.routers.chat2db.train_vanna_sql_question")
    @patch("apps.routers.chat2db.train_vanna_table")
    @patch("apps.routers.chat2db.delete_train_data")
    def test_train_table_success(self, mock_delete_train_data,
                                 mock_train_vanna_table,
                                 mock_train_vanna_sql_question,
                                 mock_set_default_backend):
        mock_delete_train_data.return_value = None
        mock_train_vanna_table.return_value = None
        mock_train_vanna_sql_question.return_value = None
        mock_set_default_backend.return_value = MagicMock()

        response = self.client.post("/chat2db/train", json={
            "table_sql": ["test_01"],
            "question_sql": [
                {
                    "question": "test_02",
                    "sql": "test_03",
                    "table": ["test_04"]
                }
            ]
        })
