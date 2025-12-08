# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 依赖注入模块"""

from apps.dependency.user import (
    is_admin,
    verify_admin,
    verify_personal_token,
)

__all__ = [
    "is_admin",
    "verify_admin",
    "verify_personal_token",
]
