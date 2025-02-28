"""测试Redis客户端

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import os
import unittest
from unittest.mock import MagicMock, patch

import redis

from apps.models.redis import RedisConnectionPool

config = {
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
    "REDIS_PWD": "password",
}

class TestRedisConnectionPool(unittest.TestCase):

    @patch("apps.models.redis_db.redis.ConnectionPool")
    @patch("apps.models.redis_db.CryptoHub.query_plaintext_by_config_name", return_value='password')
    def test_get_redis_pool(self, mock_query_plaintext, connection_pool):
        mock_connection_pool = MagicMock()
        connection_pool.return_value = mock_connection_pool

        pool = RedisConnectionPool.get_redis_pool()

        mock_query_plaintext.assert_called_once_with('REDIS_PWD')
        connection_pool.assert_called_once_with(host='localhost', port='6379', password='password')
        self.assertEqual(pool, mock_connection_pool)

    @patch('apps.models.redis_db.RedisConnectionPool.get_redis_pool')
    def test_get_redis_connection(self, mock_get_redis_pool):
        mock_pool = MagicMock()
        mock_redis_connection = MagicMock(spec=redis.Redis)
        mock_get_redis_pool.return_value = mock_pool
        mock_redis = MagicMock(return_value=mock_redis_connection)

        with patch('redis.Redis', mock_redis):
            connection = RedisConnectionPool.get_redis_connection()

        mock_get_redis_pool.assert_called_once()
        mock_redis.assert_called_once_with(connection_pool=mock_pool)
        self.assertEqual(connection, mock_redis_connection)


if __name__ == '__main__':
    unittest.main()
