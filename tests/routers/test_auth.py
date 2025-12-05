# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.

import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from apps.routers.auth import router


class TestAuthRouter(unittest.TestCase):
    """测试 auth 路由"""

    def setUp(self) -> None:
        """设置测试客户端"""
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    @patch("apps.routers.auth._check_user_group")
    @patch("apps.routers.auth.UserManager.create_or_update_on_login", new_callable=AsyncMock)
    @patch("apps.routers.auth.PersonalTokenManager.update_personal_token", new_callable=AsyncMock)
    def test_linux_login_success(
        self, mock_update_token: Any, mock_create_user: Any, mock_check_group: Any,
    ) -> None:
        """测试 Linux 用户登录成功"""
        mock_check_group.return_value = True
        mock_create_user.return_value = None
        mock_update_token.return_value = "test_token_123"

        response = self.client.get("/api/auth/login", headers={"X-Remote-User": "testuser"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "code": status.HTTP_200_OK,
            "message": "登录成功",
            "result": {"token": "test_token_123"},
        }
        mock_check_group.assert_called_once_with("testuser")
        mock_create_user.assert_called_once_with("testuser", "testuser")
        mock_update_token.assert_called_once_with("testuser")

    def test_linux_login_no_header(self) -> None:
        """测试登录时缺少 X-Remote-User header"""
        response = self.client.get("/api/auth/login")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {
            "code": status.HTTP_401_UNAUTHORIZED,
            "message": "无法获取用户信息",
            "result": {},
        }

    @patch("apps.routers.auth._check_user_group")
    def test_linux_login_user_not_in_group(self, mock_check_group: Any) -> None:
        """测试用户不在允许的用户组中"""
        mock_check_group.return_value = False

        response = self.client.get("/api/auth/login", headers={"X-Remote-User": "testuser"})

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {
            "code": status.HTTP_403_FORBIDDEN,
            "message": "您没有权限访问此系统",
            "result": {},
        }
        mock_check_group.assert_called_once_with("testuser")

    @patch("apps.routers.auth._check_user_group")
    @patch("apps.routers.auth.UserManager.create_or_update_on_login", new_callable=AsyncMock)
    @patch("apps.routers.auth.PersonalTokenManager.update_personal_token", new_callable=AsyncMock)
    def test_linux_login_token_creation_failed(
        self, mock_update_token: Any, mock_create_user: Any, mock_check_group: Any,
    ) -> None:
        """测试创建 PersonalToken 失败"""
        mock_check_group.return_value = True
        mock_create_user.return_value = None
        mock_update_token.return_value = None

        response = self.client.get("/api/auth/login", headers={"X-Remote-User": "testuser"})

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json() == {
            "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "创建Token失败",
            "result": {},
        }

    @patch("apps.routers.auth.is_admin")
    @patch("apps.routers.auth.grp.getgrnam")
    def test_check_user_group_admin(self, mock_getgrnam: Any, mock_is_admin: Any) -> None:
        """测试 _check_user_group - 管理员用户"""
        from apps.routers.auth import _check_user_group  # noqa: PLC0415

        mock_is_admin.return_value = True

        result = _check_user_group("root")

        assert result is True
        mock_is_admin.assert_called_once_with("root")
        mock_getgrnam.assert_not_called()

    @patch("apps.routers.auth.is_admin")
    @patch("apps.routers.auth.grp.getgrnam")
    def test_check_user_group_oi_member(self, mock_getgrnam: Any, mock_is_admin: Any) -> None:
        """测试 _check_user_group - oi 组成员"""
        from apps.routers.auth import _check_user_group  # noqa: PLC0415

        mock_is_admin.return_value = False
        mock_group = MagicMock()
        mock_group.gr_mem = ["testuser", "otheruser"]
        mock_getgrnam.return_value = mock_group

        result = _check_user_group("testuser")

        assert result is True
        mock_is_admin.assert_called_once_with("testuser")
        mock_getgrnam.assert_called_once_with("oi")

    @patch("apps.routers.auth.is_admin")
    @patch("apps.routers.auth.grp.getgrnam")
    def test_check_user_group_not_authorized(self, mock_getgrnam: Any, mock_is_admin: Any) -> None:
        """测试 _check_user_group - 未授权用户"""
        from apps.routers.auth import _check_user_group  # noqa: PLC0415

        mock_is_admin.return_value = False
        mock_group = MagicMock()
        mock_group.gr_mem = ["otheruser"]
        mock_getgrnam.return_value = mock_group

        result = _check_user_group("testuser")

        assert result is False

    @patch("apps.routers.auth.is_admin")
    @patch("apps.routers.auth.grp.getgrnam")
    def test_check_user_group_oi_not_exists(self, mock_getgrnam: Any, mock_is_admin: Any) -> None:
        """测试 _check_user_group - oi 组不存在"""
        from apps.routers.auth import _check_user_group  # noqa: PLC0415

        mock_is_admin.return_value = False
        mock_getgrnam.side_effect = KeyError("oi")

        result = _check_user_group("testuser")

        assert result is False

    @patch("apps.routers.auth.verify_personal_token")
    @patch("apps.routers.auth.PersonalTokenManager.update_personal_token", new_callable=AsyncMock)
    def test_change_personal_token_success(self, mock_update_token: Any) -> None:
        """测试更新 API 密钥成功"""
        mock_update_token.return_value = "new_api_key_456"

        response = self.client.post("/api/auth/key")

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["code"] == status.HTTP_200_OK
        assert response_data["message"] == "success"
        assert response_data["result"]["apiKey"] == "new_api_key_456"

    @patch("apps.routers.auth.verify_personal_token")
    @patch("apps.routers.auth.PersonalTokenManager.update_personal_token", new_callable=AsyncMock)
    def test_change_personal_token_failed(self, mock_update_token: Any) -> None:
        """测试更新 API 密钥失败"""
        mock_update_token.return_value = None

        response = self.client.post("/api/auth/key")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        response_data = response.json()
        assert response_data["code"] == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response_data["message"] == "failed to update personal token"


if __name__ == "__main__":
    unittest.main()
