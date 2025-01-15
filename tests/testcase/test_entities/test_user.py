# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from apps.entities.user import User


class TestUser(unittest.TestCase):

    def test_valid_user(self):
        user = {
            "user_sub": "1",
            "passwd": None,
            "organization": "openEuler",
            "revision_number": "0.0.0.0"
        }

        user_obj = User.model_validate(user)
        self.assertEqual(user_obj.user_sub, "1")
        self.assertEqual(user_obj.organization, "openEuler")
        self.assertEqual(user_obj.revision_number, "0.0.0.0")
        self.assertIsNone(user_obj.passwd)

    def test_invalid_user(self):
        user = {
            "user_sub": 1000,
            "passwd": "123456",
            "organization": None,
            "revision_number": "0.0.0.0"
        }

        self.assertRaises(Exception, User.model_validate, user)


if __name__ == '__main__':
    unittest.main()
