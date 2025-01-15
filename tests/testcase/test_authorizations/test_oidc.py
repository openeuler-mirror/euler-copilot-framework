# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import os
import unittest
from unittest.mock import patch, MagicMock
from http import HTTPStatus
from fastapi.exceptions import HTTPException
from apps.common.oidc import get_oidc_token, get_oidc_user
from apps.common.config import config


class TestOidcFunctions(unittest.TestCase):
    @patch('apps.auth.oidc.requests.post')
    def test_get_oidc_token(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test_access_token"}
        mock_response.status_code = HTTPStatus.OK
        mock_post.return_value = mock_response

        token = get_oidc_token("test_code")

        self.assertEqual(token, "test_access_token")
        mock_post.assert_called_once_with(
            os.getenv("OIDC_TOKEN_URL"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_id": os.getenv("OIDC_APP_ID"),
                "client_secret": config["OIDC_APP_SECRET"],
                "redirect_uri": os.getenv("OIDC_AUTH_CALLBACK_URL"),
                "grant_type": os.getenv("OIDC_TOKEN_GRANT_TYPE"),
                "code": "test_code"
            },
            stream=False,
            timeout=10
        )

    @patch('apps.auth.oidc.requests.get')
    def test_get_oidc_user(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"sub": "test_user_sub", "phone_number": "1234567890"}
        mock_response.status_code = HTTPStatus.OK
        mock_get.return_value = mock_response

        user_info = get_oidc_user("test_access_token")

        self.assertEqual(user_info, {"user_sub": "test_user_sub", "organization": "openEuler"})
        mock_get.assert_called_once_with(
            os.getenv("OIDC_USER_URL"),
            headers={"Authorization": "test_access_token"},
            timeout=10
        )

    @patch('apps.auth.oidc.requests.get')
    def test_get_oidc_user_invalid_token(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = HTTPStatus.UNAUTHORIZED
        mock_response.json.return_value = {}
        mock_get.side_effect = HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED
        )

        with self.assertRaises(HTTPException) as cm:
            get_oidc_user("test_access_token")

        self.assertEqual(cm.exception.status_code, HTTPStatus.UNAUTHORIZED)

    @patch('apps.auth.oidc.requests.get')
    def test_get_oidc_user_empty_token(self, mock_get):
        user_info = get_oidc_user("")

        self.assertEqual(user_info, {})
        mock_get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
