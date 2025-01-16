"""工具函数

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import hashlib


def get_bytes_hash(s: bytes) -> str:
    """获取字节串的哈希值"""
    return hashlib.sha256(s).hexdigest()


def get_str_hash(s: str) -> str:
    """获取字符串的哈希值"""
    return get_bytes_hash(s.encode("utf-8"))
