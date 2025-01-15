# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from unittest.mock import patch
from jwt.exceptions import InvalidSignatureError


class TimeProvider:
    @staticmethod
    def utcnow():
        return datetime.utcnow()


class TestJwtUtil(unittest.TestCase):

    def setUp(self):
        self.jwt_util = JwtUtil(key="secret_key", expires=30)
        self.payload = {"user_id": 123}

    def test_encode_decode(self):
        token = self.jwt_util.encode(self.payload)
        decoded_payload = self.jwt_util.decode(token)
        self.assertEqual(decoded_payload["user_id"], self.payload["user_id"])

    @patch('jwt.decode')
    def test_decode_invalid_signature(self, mock_jwt_decode):
        mock_jwt_decode.side_effect = InvalidSignatureError
        with self.assertRaises(InvalidSignatureError):
            self.jwt_util.decode("invalid_token")

    @patch('jwt.encode')
    def test_encode_exp(self, mock_jwt_encode):
        mock_jwt_encode.return_value = "encoded_token"
        expiration_time = datetime.utcnow() + timedelta(minutes=30)
        with patch.object(TimeProvider, 'utcnow', return_value=expiration_time):
            token = self.jwt_util.encode(self.payload)
        self.assertEqual(token, "encoded_token")


if __name__ == '__main__':
    unittest.main()
