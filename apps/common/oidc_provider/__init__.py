# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""OIDC Provider"""

from .authelia import AutheliaOIDCProvider
from .authhub import AuthhubOIDCProvider
from .base import OIDCProviderBase
from .openeuler import OpenEulerOIDCProvider

__all__ = [
    "AutheliaOIDCProvider",
    "AuthhubOIDCProvider",
    "OIDCProviderBase",
    "OpenEulerOIDCProvider",
]
