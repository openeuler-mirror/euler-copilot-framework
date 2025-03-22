"""OIDC Provider Base"""

from typing import Any


class OIDCProviderBase:
    """OIDC Provider Base"""

    @classmethod
    async def get_oidc_token(cls, code: str) -> dict[str, Any]:
        """获取OIDC Token"""
        raise NotImplementedError

    @classmethod
    async def get_oidc_user(cls, access_token: str) -> dict[str, Any]:
        """获取OIDC用户"""
        raise NotImplementedError

    @classmethod
    async def get_login_status(cls, token: str) -> bool:
        """检查登录状态"""
        raise NotImplementedError

    @classmethod
    async def oidc_logout(cls, token: str) -> None:
        """触发OIDC的登出"""
        raise NotImplementedError
