# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest

from pydantic import ValidationError

from apps.entities.error_response import ErrorResponse


class TestErrorResponse(unittest.TestCase):

    def test_valid_error_response(self):
        data = {
            "code": 404,
            "err_msg": "Not Found"
        }

        error_response = ErrorResponse.model_validate(data)
        self.assertEqual(error_response.model_dump(), data)

    def test_invalid_error_response(self):
        data = {
            "code": 400
        }
        self.assertRaises(Exception, ErrorResponse.model_validate, data)


if __name__ == '__main__':
    unittest.main()
