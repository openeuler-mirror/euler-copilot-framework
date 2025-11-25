# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""OIDC Provider"""

from .authhub import AuthhubOIDCProvider
from .base import OIDCProviderBase

__all__ = [
    "AuthhubOIDCProvider",
    "OIDCProviderBase",
]
