"""加密解密模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import hashlib

from apps.common.security import Security


class CryptoHub:
    """加密解密模块"""

    @staticmethod
    def generate_str_from_sha256(plain_txt: str) -> str:
        """生成文本的SHA256哈希值"""
        hash_object = hashlib.sha256(plain_txt.encode("utf-8"))
        hex_dig = hash_object.hexdigest()
        return hex_dig[:]

    @staticmethod
    def decrypt_with_config(encrypted_plaintext: list) -> str:
        """解密密文"""
        secret_dict_key_list = [
            "encrypted_work_key",
            "encrypted_work_key_iv",
            "encrypted_iv",
            "half_key1",
        ]
        encryption_config = {}
        for key in secret_dict_key_list:
            encryption_config[key] = encrypted_plaintext[1][CryptoHub.generate_str_from_sha256(key)]
        plaintext = Security.decrypt(encrypted_plaintext[0], encryption_config)
        del encryption_config
        return plaintext
