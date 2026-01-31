"""
日志脱敏模块

对敏感信息进行脱敏处理，防止日志泄露。
"""

from __future__ import annotations

import logging
import re
from typing import Any, ClassVar, Final

logger = logging.getLogger(__name__)


class LogRedactor:
    """
    日志脱敏器

    自动识别并脱敏敏感信息：
    - 密码相关字段（password, passwd, pwd, secret, token, key, api_key 等）
    - Authorization header
    - 特定模式（JWT token, API key 格式等）
    """

    # 敏感字段关键词（不区分大小写）
    SENSITIVE_KEYWORDS: ClassVar[frozenset[str]] = frozenset(
        [
            "password",
            "passwd",
            "pwd",
            "secret",
            "token",
            "api_key",
            "apikey",
            "api-key",
            "access_key",
            "accesskey",
            "access-key",
            "private_key",
            "privatekey",
            "private-key",
            "credential",
            "auth",
            "authorization",
            "bearer",
        ]
    )

    # 敏感模式正则
    SENSITIVE_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        # JWT token
        re.compile(r"eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*"),
        # Bearer token
        re.compile(r"Bearer\s+[A-Za-z0-9_-]+", re.IGNORECASE),
        # API key 格式（常见格式）
        re.compile(r"sk-[A-Za-z0-9]{32,}"),  # OpenAI style
        re.compile(r"ghp_[A-Za-z0-9]{36}"),  # GitHub Personal Access Token
        re.compile(r"gho_[A-Za-z0-9]{36}"),  # GitHub OAuth Token
    ]

    MASK: Final[str] = "***REDACTED***"
    MASK_SHORT: Final[str] = "***"

    def __init__(
        self,
        extra_keywords: set[str] | None = None,
        mask: str = MASK,
    ) -> None:
        """
        初始化脱敏器

        Args:
            extra_keywords: 额外的敏感关键词
            mask: 脱敏替换字符串

        """
        self._keywords = set(self.SENSITIVE_KEYWORDS)
        if extra_keywords:
            self._keywords.update(kw.lower() for kw in extra_keywords)
        self._mask = mask

    def is_sensitive_key(self, key: str) -> bool:
        """
        检查键名是否敏感

        Args:
            key: 键名

        Returns:
            是否敏感

        """
        key_lower = key.lower()
        return any(kw in key_lower for kw in self._keywords)

    def redact_value(self, value: str) -> str:
        """
        脱敏单个值

        Args:
            value: 原始值

        Returns:
            脱敏后的值

        """
        if not isinstance(value, str):
            return value

        result = value
        for pattern in self.SENSITIVE_PATTERNS:
            result = pattern.sub(self._mask, result)

        return result

    def redact_dict(self, data: dict[str, Any], *, in_place: bool = False) -> dict[str, Any]:
        """
        脱敏字典

        Args:
            data: 原始字典
            in_place: 是否原地修改

        Returns:
            脱敏后的字典

        """
        if not in_place:
            data = dict(data)

        for key, value in data.items():
            if self.is_sensitive_key(key):
                data[key] = self.MASK_SHORT
            elif isinstance(value, str):
                data[key] = self.redact_value(value)
            elif isinstance(value, dict):
                data[key] = self.redact_dict(value, in_place=False)
            elif isinstance(value, list):
                data[key] = [
                    self.redact_dict(v, in_place=False)
                    if isinstance(v, dict)
                    else self.redact_value(v)
                    if isinstance(v, str)
                    else v
                    for v in value
                ]

        return data

    def redact_env(self, env: dict[str, str]) -> dict[str, str]:
        """
        脱敏环境变量

        Args:
            env: 环境变量字典

        Returns:
            脱敏后的环境变量

        """
        result = {}
        for key, value in env.items():
            if self.is_sensitive_key(key):
                result[key] = self.MASK_SHORT
            else:
                result[key] = self.redact_value(value)
        return result

    def redact_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """
        脱敏 HTTP 请求头

        Args:
            headers: 请求头字典

        Returns:
            脱敏后的请求头

        """
        result: dict[str, str] = {}
        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower in ("authorization", "x-api-key", "x-auth-token") or self.is_sensitive_key(key):
                result[key] = self.MASK_SHORT
            else:
                result[key] = self.redact_value(value)
        return result

    def safe_log(self, message: str, data: dict[str, Any] | None = None) -> str:
        """
        生成安全的日志消息

        Args:
            message: 日志消息
            data: 附加数据

        Returns:
            脱敏后的日志消息

        """
        if data:
            redacted = self.redact_dict(data)
            return f"{message}: {redacted}"
        return message


# 全局默认脱敏器单例
class _RedactorSingleton:
    """Redactor 单例容器"""

    _instance: LogRedactor | None = None

    @classmethod
    def get(cls) -> LogRedactor:
        """获取单例"""
        if cls._instance is None:
            cls._instance = LogRedactor()
        return cls._instance


def get_redactor() -> LogRedactor:
    """获取全局脱敏器"""
    return _RedactorSingleton.get()


def redact(data: dict[str, Any]) -> dict[str, Any]:
    """快捷脱敏函数"""
    return get_redactor().redact_dict(data)
