"""API Key Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import hashlib
import logging
import uuid
from typing import Optional

from apps.models.mongo import MongoDB

logger = logging.getLogger("ray")


class ApiKeyManager:
    """API Key管理"""

    @staticmethod
    async def generate_api_key(user_sub: str) -> Optional[str]:
        """生成新API Key"""
        api_key = str(uuid.uuid4().hex)
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]

        try:
            user_collection = MongoDB.get_collection("user")
            await user_collection.update_one(
                {"_id": user_sub},
                {"$set": {"api_key": api_key_hash}},
            )
            return api_key
        except Exception:
            logger.exception("[ApiKeyManager] 生成API Key失败")
            return None

    @staticmethod
    async def delete_api_key(user_sub: str) -> bool:
        """删除API Key"""
        if not await ApiKeyManager.api_key_exists(user_sub):
            return False
        try:
            user_collection = MongoDB.get_collection("user")
            await user_collection.update_one(
                {"_id": user_sub},
                {"$unset": {"api_key": ""}},
            )
        except Exception:
            logger.exception("[ApiKeyManager] 删除API Key失败")
            return False
        return True

    @staticmethod
    async def api_key_exists(user_sub: str) -> bool:
        """检查API Key是否存在"""
        try:
            user_collection = MongoDB.get_collection("user")
            user_data = await user_collection.find_one({"_id": user_sub}, {"_id": 0, "api_key": 1})
            return user_data is not None and ("api_key" in user_data and user_data["api_key"])
        except Exception:
            logger.exception("[ApiKeyManager] 检查API Key是否存在失败")
            return False

    @staticmethod
    async def get_user_by_api_key(api_key: str) -> Optional[str]:
        """根据API Key获取用户信息"""
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        try:
            user_collection = MongoDB.get_collection("user")
            user_data = await user_collection.find_one({"api_key": api_key_hash}, {"_id": 1})
            return user_data["_id"] if user_data else None
        except Exception:
            logger.exception("[ApiKeyManager] 根据API Key获取用户信息失败")
            return None

    @staticmethod
    async def verify_api_key(api_key: str) -> bool:
        """验证API Key，用于FastAPI dependency"""
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        try:
            user_collection = MongoDB.get_collection("user")
            key_data = await user_collection.find_one({"api_key": api_key_hash}, {"_id": 1})
            return key_data is not None
        except Exception:
            logger.exception("[ApiKeyManager] 验证API Key失败")
            return False

    @staticmethod
    async def update_api_key(user_sub: str) -> Optional[str]:
        """更新API Key"""
        if not await ApiKeyManager.api_key_exists(user_sub):
            return None
        api_key = str(uuid.uuid4().hex)
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        try:
            user_collection = MongoDB.get_collection("user")
            await user_collection.update_one(
                {"_id": user_sub},
                {"$set": {"api_key": api_key_hash}},
            )
        except Exception:
            logger.exception("[ApiKeyManager] 更新API Key失败")
            return None
        return api_key
