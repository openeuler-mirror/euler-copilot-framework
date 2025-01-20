"""工具函数

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from hashlib import sha256, shake_128


def get_short_hash(s: bytes) -> str:
    """获取字节串的哈希值"""
    return shake_128(s).hexdigest(8)


def get_long_hash(s: bytes) -> str:
    """获取字节串的哈希值"""
    return sha256(s).hexdigest()
