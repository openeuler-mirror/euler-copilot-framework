# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from unittest.mock import MagicMock, patch

from apps.common.cryptohub import CryptoHub


class TestCryptoHub(unittest.TestCase):

    def setUp(self):
        self.test_dir = "test_dir"
        self.test_config_name = "test_config"
        self.test_plain_text = "test_plain_text"
        self.test_encrypted_plaintext = "test_encrypted_plaintext"
        self.test_config_dir = "test_config_dir"
        self.test_config_deletion_flag = False

    def test_generate_str_from_sha256(self):
        result = CryptoHub.generate_str_from_sha256(self.test_plain_text)
        self.assertIsInstance(result, str)

    def test_generate_key_config(self):
        with patch('os.mkdir'), patch('os.path.join'), patch('os.getcwd') as mock_getcwd:
            mock_getcwd.return_value = self.test_dir
            result, config_dir = CryptoHub.generate_key_config(self.test_config_name, self.test_plain_text)
            self.assertIsInstance(result, str)
            self.assertIsInstance(config_dir, str)

    def test_decrypt_with_config(self):
        with patch('os.path.join') as mock_join, patch('os.path.dirname') as mock_dirname:
            mock_join.return_value = self.test_config_dir
            mock_dirname.return_value = self.test_dir
            result = CryptoHub.decrypt_with_config(self.test_config_dir, self.test_encrypted_plaintext,
                                                   self.test_config_deletion_flag)
            self.assertIsInstance(result, str)

    def test_generate_key_config_from_file(self):
        with patch('os.listdir') as mock_listdir, patch('os.path.join') as mock_join, patch(
                'os.path.basename') as mock_basename:
            mock_listdir.return_value = ['file1.json']
            mock_join.return_value = self.test_dir
            mock_basename.return_value = "test_config_name.json"
            CryptoHub.generate_key_config_from_file(self.test_dir)

    def test_query_plaintext_by_config_name(self):
        with patch('json.load') as mock_load, patch('os.path.join') as mock_join, patch(
                'os.path.dirname') as mock_dirname:
            mock_load.return_value = {
                CryptoHub.generate_str_from_sha256(self.test_config_name): {
                    CryptoHub.generate_str_from_sha256('encrypted_plaintext'): self.test_encrypted_plaintext,
                    CryptoHub.generate_str_from_sha256('key_config_dir'): self.test_config_dir,
                    CryptoHub.generate_str_from_sha256('config_deletion_flag'): self.test_config_deletion_flag
                }
            }
            mock_join.return_value = self.test_dir
            mock_dirname.return_value = self.test_dir
            result = CryptoHub.query_plaintext_by_config_name(self.test_config_name)
            self.assertIsInstance(result, str)

    def test_add_plaintext_to_env(self):
        with patch('os.path.join') as mock_join, patch('os.path.dirname') as mock_dirname, patch(
                'os.open') as mock_open, patch('os.fdopen') as mock_fdopen, patch('json.load') as mock_load:
            mock_join.return_value = self.test_dir
            mock_dirname.return_value = self.test_dir
            mock_open.return_value = 1
            mock_fdopen.return_value = MagicMock(spec=open)
            mock_load.return_value = {
                CryptoHub.generate_str_from_sha256(self.test_config_name): {
                    CryptoHub.generate_str_from_sha256('encrypted_plaintext'): self.test_encrypted_plaintext,
                    CryptoHub.generate_str_from_sha256('key_config_dir'): self.test_config_dir,
                    CryptoHub.generate_str_from_sha256('config_deletion_flag'): self.test_config_deletion_flag
                }
            }
            CryptoHub.add_plaintext_to_env(self.test_dir)


if __name__ == '__main__':
    unittest.main()
