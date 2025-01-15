# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
import unittest
from unittest.mock import patch

from apps.common.security import Security


class TestSecurity(unittest.TestCase):

    def test_encrypt(self):
        plaintext = "test_plaintext"
        encrypted_plaintext, secret_dict = Security.encrypt(plaintext)
        self.assertIsInstance(encrypted_plaintext, str)
        self.assertIsInstance(secret_dict, dict)

    def test_decrypt(self):
        encrypted_plaintext = "encrypted_plaintext"
        secret_dict = {
            "encrypted_work_key": "encrypted_work_key",
            "encrypted_work_key_iv": "encrypted_work_key_iv",
            "encrypted_iv": "encrypted_iv",
            "half_key1": "half_key1"
        }

        # 模拟 Security 类中相关方法的行为
        with patch('apps.common.security.Security._decrypt_plaintext', return_value="decrypted_plaintext"):
            plaintext = Security.decrypt(encrypted_plaintext, secret_dict)

        self.assertEqual(plaintext, "decrypted_plaintext")


if __name__ == "__main__":
    unittest.main()
