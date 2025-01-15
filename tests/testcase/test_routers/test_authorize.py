# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from jwt import encode

from apps.routers.auth import router

access_token = encode({"sub": "user_id"}, "secret_key", algorithm="HS256")


class TestAuthorizeRouter(unittest.TestCase):

    @patch('apps.routers.authorize.get_oidc_token')
    @patch('apps.routers.authorize.get_oidc_user')
    @patch('apps.routers.authorize.RedisConnectionPool.get_redis_connection')
    @patch('apps.routers.authorize.UserManager.update_userinfo_by_user_sub')
    def test_oidc_login_success(self, mock_update_userinfo, mock_get_redis_connection, mock_get_oidc_user,
                                mock_get_oidc_token):
        client = TestClient(router)
        mock_update_userinfo.return_value = None
        mock_get_oidc_token.return_value = "access_token"
        mock_get_oidc_user.return_value = {'user_sub': '123'}
        mock_redis = MagicMock()
        mock_get_redis_connection.return_value = mock_redis
        mock_redis.setex.return_value = None
        response = client.get("/authorize/login?code=123")
        assert response.status_code == 200
        assert mock_update_userinfo.call_count == 1
        assert mock_redis.setex.call_count == 2

    @patch('apps.routers.authorize.RedisConnectionPool.get_redis_connection')
    def test_oidc_login_fail(self, mock_get_redis_connection):
        client = TestClient(router)
        mock_redis = MagicMock()
        mock_get_redis_connection.return_value = mock_redis
        mock_redis.setex.return_value = None
        response = client.get("/authorize/login?code=123")
        assert response.status_code == 200
        assert response.json() == {
            "code": 400,
            "err_msg": "OIDC login failed."
        }
        assert mock_redis.setex.call_count == 0

    @patch('apps.routers.authorize.RedisConnectionPool.get_redis_connection')
    def test_logout(self, mock_get_redis_connection):
        client = TestClient(router)
        mock_redis = MagicMock()
        mock_get_redis_connection.return_value = mock_redis
        mock_redis.delete.return_value = None
        response = client.get("/authorize/logout", cookies={"_t": access_token})
        assert response.status_code == 200
        assert response.json() == {
            "code": 200,
            "message": "success",
            "result": {}
        }
        assert mock_redis.delete.call_count == 2

    @patch('apps.routers.authorize.UserManager.get_revision_number_by_user_sub')
    def test_userinfo(self, mock_get_revision_number_by_user_sub):
        client = TestClient(router)
        mock_get_revision_number_by_user_sub.return_value = "123"
        response = client.get("/authorize/user", cookies={"_t": "access_token"})
        assert response.status_code == 200
        assert response.json() == {
            "code": 200,
            "message": "success",
            "result": {"user_sub": "123", "organization": "example", "revision_number": "123"}
        }

    @patch('apps.routers.authorize.UserManager.update_userinfo_by_user_sub')
    def test_update_revision_number(self, mock_update_userinfo_by_user_sub):
        client = TestClient(router)
        mock_update_userinfo_by_user_sub.return_value = None
        response = client.post("/authorize/update_revision_number", json={"revision_num": "123"},
                               cookies={"_t": "access_token"})
        assert response.status_code == 200
        assert response.json() == {
            "code": 200,
            "message": "success",
            "result": {"user_sub": "123", "organization": "example", "revision_number": "123"}
        }


if __name__ == '__main__':
    unittest.main()
