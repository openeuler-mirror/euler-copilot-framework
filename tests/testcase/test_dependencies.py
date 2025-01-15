# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import asyncio
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from fastapi import HTTPException, Request, Response, status
from jwt import PyJWTError

from apps.dependency import User, UserManager, get_current_user, moving_window_limit


# 在测试函数外部定义一个异步运行函数
async def run_test(decorated_func, request, user):
    return await decorated_func(request, user=user)


class TestDependencies(unittest.TestCase):

    def setUp(self):
        self.request = MagicMock(spec=Request)
        self.response = MagicMock(spec=Response)

    @patch('apps.dependencies.JwtUtil')
    @patch('apps.dependencies.RedisConnectionPool')
    def test_get_current_user_token_validation(self, mock_redis_pool, mock_jwt_util):
        # 模拟 token 和 user_info
        token = b"mock_token"
        user_sub = "mock_user_sub"
        user_info = {"user_sub": user_sub, "other_info": "mock_info"}
        payload = {"user_sub": user_sub}

        # 模拟请求对象
        mock_request = MagicMock()
        mock_request.cookies.get.return_value = token
        mock_request.get.return_value = '/authorize/refresh_token'

        # 模拟 JwtUtil 的 decode 方法
        mock_jwt_util.return_value.decode.return_value = payload

        # 模拟 Redis 连接池和连接对象
        mock_connection = MagicMock()
        mock_connection.get.return_value = b"mock_token"  # 模拟从Redis中获取的令牌值
        mock_redis_pool.return_value.get_redis_connection.return_value = mock_connection

        # 调用函数，并捕获异常
        try:
            get_current_user(mock_request)
        except HTTPException as e:
            # 断言是否抛出了 HTTPException，并验证异常消息
            self.assertEqual(e.detail, "need logout oidc")
            self.assertEqual(e.status_code, 460)
        else:
            self.fail("Expected HTTPException was not raised")

    @patch("apps.dependencies.JwtUtil")
    def test_get_current_user_invalid_token(self, mock_jwt_util):
        # Mocking invalid token
        token = "invalid_token"
        self.request.cookies.get.return_value = token
        mock_jwt_util.return_value.decode.side_effect = PyJWTError

        # Call the function and expect HTTPException
        with self.assertRaises(HTTPException):
            get_current_user(self.request)

    @patch("apps.dependencies.RedisConnectionPool")
    async def test_moving_window_limit_within_limit(self, mock_redis_pool):
        # Mock Redis connection
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis_pool.get_redis_connection.return_value = mock_redis

        # Mock the wrapped function
        async def mock_func(*args, **kwargs):
            return "Mock response"

        # Decorate the function
        decorated_func = moving_window_limit(mock_func)

        # 创建一个完整的 User 对象
        complete_user = User(user_sub='sub_value', organization='org_value')

        # Call the decorated function
        response = await decorated_func(self.request, user=complete_user)

        # Assertions
        self.assertEqual(response, "Mock response")

    @patch("apps.dependencies.RedisConnectionPool")
    def test_moving_window_limit_exceed_limit(self, mock_redis_pool):
        # Mock Redis connection
        mock_redis = MagicMock()
        mock_redis.get.return_value = b"stream_answer"
        mock_redis_pool.get_redis_connection.return_value = mock_redis

        # Mock the wrapped function
        async def mock_func(*args, **kwargs):
            return "Mock response"

        # Decorate the function
        decorated_func = moving_window_limit(mock_func)

        # 创建一个完整的 User 对象
        complete_user = User(user_sub='sub_value', organization='org_value')

        # 调用异步运行函数，并使用 asyncio.run() 运行
        response = asyncio.run(run_test(decorated_func, self.request, user=complete_user))

        # 确保在测试中正确处理了异步函数的返回值
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.body, b"Rate limit exceeded")


if __name__ == '__main__':
    unittest.main()
