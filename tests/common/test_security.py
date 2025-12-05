"""
测试 Security 类

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""
import pytest
from pytest_mock import MockerFixture

from apps.common.security import Security


def test_encrypt() -> None:
    """测试加密功能"""
    plaintext = "test_plaintext"
    encrypted_plaintext, secret_dict = Security.encrypt(plaintext)
    assert isinstance(encrypted_plaintext, str)
    assert isinstance(secret_dict, dict)


def test_decrypt(mocker: MockerFixture) -> None:
    """测试解密功能"""
    encrypted_plaintext = "encrypted_plaintext"
    secret_dict = {
        "encrypted_work_key": "encrypted_work_key",
        "encrypted_work_key_iv": "encrypted_work_key_iv",
        "encrypted_iv": "encrypted_iv",
        "half_key1": "half_key1",
    }

    # 模拟 Security 类中相关方法的行为
    mocker.patch("apps.common.security.Security._decrypt_plaintext", return_value="decrypted_plaintext")
    plaintext = Security.decrypt(encrypted_plaintext, secret_dict)

    assert plaintext == "decrypted_plaintext"


if __name__ == "__main__":
    pytest.main([__file__])
