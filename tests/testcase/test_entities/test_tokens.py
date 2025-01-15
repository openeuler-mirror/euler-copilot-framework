# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from apps.entities.tokens import TokensResponse


class TestTokensResponse(unittest.TestCase):

    def test_valid_token(self):
        data = {
            "csrf_token": "csrf_token_value"
        }
        tokens_response = TokensResponse.model_validate(data)
        self.assertEqual(tokens_response.csrf_token, "csrf_token_value")

    def test_invalid_token(self):
        data = {
            "csrf_token": None
        }

        self.assertRaises(Exception, TokensResponse.model_validate, data)


if __name__ == '__main__':
    unittest.main()
